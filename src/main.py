import streamlit as st
from typing import NoReturn

from ui import create_new_chat, display_home, display_thread, select_thread_sidebar, ensure_navigation_state, manage_files
from utils import get_or_create_user_from_google
from models import User

def main() -> NoReturn:
    """
    Main function to run the Streamlit application.
    
    This function initializes the application, handles user authentication,
    manages navigation between different pages, and displays the appropriate
    UI components based on the current page.
    
    Returns:
        NoReturn: This function runs continuously as a Streamlit app
    """
    # Initialize session state for navigation if not exists
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    
    # Check if user is logged in
    if not st.experimental_user.is_logged_in:
        # Display login option
        st.title("Study Buddy")
        st.header("Welcome to Study Buddy!")
        st.write("Study Buddy is an AI-powered chat application that helps students learn and study effectively using their own study materials.")
        st.write("Please log in with your Google account to get started.")
        
        if st.button("Log in with Google"):
            st.login()
            
        # Show information about the app for unauthenticated users
        st.subheader("What is Study Buddy?")
        st.write("""
        Study Buddy helps you:
        - Upload your study materials (PDF, TXT) for AI-assisted learning
        - Organize your learning with personalized study sessions
        - Chat with an AI tutor that references your materials
        - Review and continue previous study conversations
        """)
    else:
        # User is authenticated - access user information
        user_email = st.experimental_user.email
        user_name = st.experimental_user.name
        
        # Get or create user in database
        current_user: User = get_or_create_user_from_google(user_email, user_name)
        
        # Sidebar for navigation after successful login
        st.sidebar.title(f"Welcome, {user_name}!")
        
        # Logout button in sidebar
        if st.sidebar.button("Logout"):
            st.logout()
        
        # Check for redirect flags from session creation
        if st.session_state.get('redirect_to_sessions', False):
            ensure_navigation_state("Previous Sessions")
            # Clear the flag after using it
            st.session_state.pop('redirect_to_sessions')
            st.rerun()  # Force a rerun to ensure the UI updates immediately
        
        # Navigation in sidebar with session state to remember selection
        app_page = st.sidebar.radio(
            "Navigation Menu",
            ["Home", "New Study Session", "Previous Sessions", "Manage Files"],
            index=["Home", "New Study Session", "Previous Sessions", "Manage Files"].index(st.session_state.current_page) 
            if st.session_state.current_page in ["Home", "New Study Session", "Previous Sessions", "Manage Files"] else 0
        )
        
        # Only update navigation state if it has changed
        if app_page != st.session_state.current_page:
            ensure_navigation_state(app_page)
            st.rerun()  # Force a rerun to ensure the UI updates immediately
        
        # Display the appropriate page based on the navigation state
        if st.session_state.current_page == "Home":
            display_home(current_user)
        elif st.session_state.current_page == "New Study Session":
            create_new_chat(current_user)
        elif st.session_state.current_page == "Previous Sessions":
            selected_thread = select_thread_sidebar(current_user)
            if selected_thread:
                display_thread(selected_thread)
            else:
                st.info("No previous study sessions found. Start by creating a new study session!")
        elif st.session_state.current_page == "Manage Files":
            manage_files(current_user)

if __name__ == "__main__":
    main()
