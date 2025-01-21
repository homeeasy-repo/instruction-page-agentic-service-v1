import streamlit as st
import psycopg2
from datetime import datetime
import pandas as pd
import hashlib

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

DATABASE_URL = {
    'dbname': st.secrets["database"]["DB_NAME"],
    'user': st.secrets["database"]["DB_USER"],
    'password': st.secrets["database"]["DB_PASSWORD"],
    'host': st.secrets["database"]["DB_HOST"],
    'port': st.secrets["database"]["DB_PORT"]
}

def get_db_connection():
    return psycopg2.connect(**DATABASE_URL)

def verify_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cur.execute("""
            SELECT 1 FROM app_users 
            WHERE username = %s AND password_hash = %s
        """, (username, password_hash))
        result = cur.fetchone()
        return result is not None
    except Exception as e:
        st.error(f"Database error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def login_page():
    st.title("Login")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if verify_user(username, password):
            st.session_state.authenticated = True
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid username or password")

def get_current_instructions():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, instruction_name, instruction_text, created_at 
        FROM amy_instructions 
        ORDER BY id;
    """)
    instructions = cur.fetchall()
    cur.close()
    conn.close()
    return instructions

def get_instruction_history(instruction_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT instruction_name, instruction_text, created_at 
        FROM instruction_history 
        WHERE instruction_id = %s 
        ORDER BY created_at DESC;
    """, (instruction_id,))
    history = cur.fetchall()
    cur.close()
    conn.close()
    return history

def update_instruction(instruction_id, new_name, new_instruction):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get current instruction before updating
    cur.execute("""
        SELECT instruction_name, instruction_text 
        FROM amy_instructions 
        WHERE id = %s
    """, (instruction_id,))
    current = cur.fetchone()
    current_name, current_text = current
    
    # Save current version to history
    cur.execute("""
        INSERT INTO instruction_history 
        (instruction_id, instruction_name, instruction_text)
        VALUES (%s, %s, %s);
    """, (instruction_id, current_name, current_text))
    
    # Update current instruction
    cur.execute("""
        UPDATE amy_instructions 
        SET instruction_name = %s,
            instruction_text = %s,
            created_at = CURRENT_TIMESTAMP
        WHERE id = %s;
    """, (new_name, new_instruction, instruction_id))
    
    conn.commit()
    cur.close()
    conn.close()

def Amy_Instructions():
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Add logout button in the sidebar
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()
    
    st.title("Agent Instructions Management")
    
    instructions = get_current_instructions()
    
    st.header("Current Instructions")
    
    tab1, tab2 = st.tabs(["Current Instructions", "History"])
    
    with tab1:
        for inst in instructions:
            instruction_id, name, text, created_at = inst
            
            st.subheader(f"Agent: {name}")
            st.text(f"Last Updated: {created_at}")
            
            new_name = st.text_input(
                "Agent Name",
                name,
                key=f"name_{instruction_id}"
            )
            
            new_instruction = st.text_area(
                "Instruction",
                text,
                key=f"instruction_{instruction_id}",
                height=150
            )
            
            if st.button("Update", key=f"update_{instruction_id}"):
                if new_instruction != text or new_name != name:
                    update_instruction(instruction_id, new_name, new_instruction)
                    st.success("Updated successfully!")
                    st.rerun()
            
            st.markdown("---")
    
    with tab2:
        agent_names = {inst[0]: inst[1] for inst in instructions}
        selected_agent = st.selectbox(
            "Select Agent to View History",
            options=list(agent_names.keys()),
            format_func=lambda x: agent_names[x]
        )
        
        if selected_agent:
            history = get_instruction_history(selected_agent)
            if history:
                st.write("Previous Versions:")
                for hist_name, hist_text, hist_date in history:
                    st.markdown(f"### Version from {hist_date}")
                    st.text(f"Agent Name: {hist_name}")
                    st.text_area(
                        "Historical Instruction",
                        hist_text,
                        key=f"hist_{selected_agent}_{hist_date}",
                        height=100
                    )
                    if st.button(
                        "Restore this version",
                        key=f"restore_{selected_agent}_{hist_date}"
                    ):
                        update_instruction(selected_agent, hist_name, hist_text)
                        st.success("Version restored!")
                        st.rerun()
                    st.markdown("---")
            else:
                st.info("No previous versions found for this agent")

if __name__ == "__main__":
    Amy_Instructions()