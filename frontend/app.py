import streamlit as st
import requests
import pandas as pd
import altair as alt

# --- CONFIGURATION ---
API_BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{API_BASE_URL}/chat"
LOGS_ENDPOINT = f"{API_BASE_URL}/activity_logs"
STATS_ENDPOINT = f"{API_BASE_URL}/stats"

st.set_page_config(page_title="Local LLM Firewall", page_icon="🛡️", layout="wide")

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🛡️ Firewall Control")
app_mode = st.sidebar.radio(
    "Choose Mode:",
    ["🤖 Client Chat Mode", "🛡️ Firewall Admin Panel"]
)

st.sidebar.markdown("---")
st.sidebar.info("Phase 2: SOC Upgrade\n\nConnected to: localhost:8000")

# --- MODE 1: CLIENT CHAT MODE ---
if app_mode == "🤖 Client Chat Mode":
    st.title("🤖 Secure Chat")
    st.caption("Protected by Local LLM Firewall")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message.get("is_blocked"):
                st.error(message["content"], icon="🚫")
            else:
                st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Message Mistral..."):
        # Add user message to state
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call Backend
        try:
            with st.spinner("Thinking..."):
                response = requests.post(CHAT_ENDPOINT, json={"user_prompt": prompt})

            if response.status_code == 200:
                data = response.json()
                bot_reply = data.get("response", "")
                
                with st.chat_message("assistant"):
                    st.markdown(bot_reply)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": bot_reply,
                    "is_blocked": False,
                    "firewall_data": {
                        "original": data.get("original_prompt", ""),
                        "sanitized": data.get("sanitized_prompt", "")
                    }
                })

            elif response.status_code == 403:
                # Security Violation Handling
                warning_msg = "🚫 SECURITY ALERT: Your message was intercepted by the Firewall."
                with st.chat_message("assistant"):
                    st.error(warning_msg, icon="🚫")
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": warning_msg,
                    "is_blocked": True
                })

            else:
                st.error(f"Error {response.status_code}: {response.text}")

        except requests.exceptions.ConnectionError:
            st.error("🚨 Connection Error: Cannot reach Firewall Backend.")


# --- MODE 2: FIREWALL ADMIN PANEL ---
elif app_mode == "🛡️ Firewall Admin Panel":
    st.title("🛡️ Security Operations Center (SOC)")
    
    # Refresh Button
    if st.button("🔄 Refresh Data"):
        st.rerun()

    # Fetch Stats
    try:
        stats_res = requests.get(STATS_ENDPOINT)
        if stats_res.status_code == 200:
            stats = stats_res.json()
        else:
            stats = {"total_requests": 0, "total_blocked": 0, "percentage_blocked": 0}
            st.error("Failed to fetch stats.")
    except:
        stats = {"total_requests": 0, "total_blocked": 0, "percentage_blocked": 0}
        st.error("Backend offline.")

    # 1. KPI Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Requests", stats['total_requests'])
    col2.metric("Total Attacks Prevented", stats['total_blocked'], delta_color="inverse")
    col3.metric("Traffic Blocked", f"{stats['percentage_blocked']}%")
    
    st.markdown("---")

    # 2. Live Traffic Table
    st.subheader("📡 Live Traffic Logs")
    try:
        logs_res = requests.get(LOGS_ENDPOINT)
        if logs_res.status_code == 200:
            logs = logs_res.json()
            if logs:
                df = pd.DataFrame(logs)
                # Reorder columns
                df = df[['timestamp', 'blocked', 'violation_type', 'user_input']]
                
                # Style the dataframe
                def highlight_blocked(row):
                    color = '#ff4b4b20' if row['blocked'] else '#21c35420'
                    return [f'background-color: {color}' for _ in row]

                st.dataframe(
                    df.style.apply(highlight_blocked, axis=1),
                    use_container_width=True,
                    height=400
                )
                
                # 3. Attack Distribution Chart
                st.subheader("📊 Threat Analysis")
                
                # Filter for blocked only to see attack types
                blocked_df = df[df['blocked'] == 1]
                if not blocked_df.empty:
                    chart = alt.Chart(blocked_df).mark_bar().encode(
                        x=alt.X('violation_type', title='Violation Type'),
                        y=alt.Y('count()', title='Count'),
                        color=alt.Color('violation_type', scale=alt.Scale(scheme='reds'))
                    ).properties(title="Attack Type Distribution")
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info("No attacks detected yet.")
            else:
                st.info("No logs found.")
    except Exception as e:
        st.error(f"Error loading logs: {e}")
