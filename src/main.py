import streamlit as st
import streamlit_authenticator as stauth

from config import config
from ui import create_new_chat, display_home, display_thread, select_thread_sidebar
from utils import get_current_user, save_user

def main():
    """Main function to run the Streamlit app."""
    # Initialize the authenticator object using the credentials from the config
    authenticator = stauth.Authenticate(
        'config.yaml',
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

    # Access the authentication status from st.session_state
    authentication_status = st.session_state.get('authentication_status')

    # If the user is authenticated, hide login/register and show the app content
    if authentication_status:
        # Sidebar for navigation after successful login
        st.sidebar.title(f"Welcome, {st.session_state['name']}")
        authenticator.logout('Logout', 'sidebar')

        # Get current user details based on the username (stored in session state)
        current_user = get_current_user(st.session_state['username'])

        # Navigation in sidebar
        app_page = st.sidebar.radio("Navigate to", ["Home", "New Chat", "Chat History"])

        if app_page == "Home":
            display_home(current_user)
        elif app_page == "New Chat":
            create_new_chat(current_user)
        elif app_page == "Chat History":
            selected_thread = select_thread_sidebar(current_user)
            if selected_thread:
                display_thread(selected_thread)
            else:
                st.info("No thread selected or no threads available. Start by creating a new chat.")

    # If the user is not authenticated, show login/register options
    else:
        # Option for Login or Registration
        page = st.sidebar.radio("Choose Action", ["Login", "Register"])

        if page == "Login":
            # Authentication process (No need to unpack return values when using 'main')
            authenticator.login('main')

            # Handle authentication status from session state
            if st.session_state.get('authentication_status') == False:
                st.error("Username/password is incorrect")
            elif st.session_state.get('authentication_status') is None:
                st.warning("Please enter your username and password")

        elif page == "Register":
            st.title("Register")
            # Allow new user registration even if credentials exist
            try:
                email, username, name = authenticator.register_user(location='main', key='register')
                if email:
                    st.success("User registered successfully! You can now log in.")
                    # Save the user to MongoDB
                    save_user(username, name, email)
            except Exception as e:
                st.error(f"Registration failed: {str(e)}")

if __name__ == "__main__":
    main()