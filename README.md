# Study Buddy

Study Buddy is an AI-powered chat application that helps students learn and study effectively using their own study materials. By leveraging OpenAI's Assistants API v2, it provides an interactive learning experience tailored to your uploaded content.

## Features

- Secure user authentication and registration system
- Upload your study materials (PDF, TXT) for AI-assisted learning
- Organize your learning with personalized study sessions
- Chat with an AI tutor that references your materials
- Review and continue previous study conversations
- User-friendly interface built with Streamlit

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/rebornify/study-buddy.git
   ```

2. Navigate to the project directory:
   ```
   cd study-buddy
   ```

3. Create a virtual environment:
   ```
   python -m venv .venv
   ```

4. Activate the virtual environment:
   - For Windows:
     ```
     .venv\Scripts\activate
     ```
   - For macOS and Linux:
     ```
     source .venv/bin/activate
     ```

5. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

6. Set up your environment variables:
   - Create a `.env` file in the project root directory with the following content:
     ```
     OPENAI_API_KEY=your-openai-api-key
     MONGODB_URI=mongodb://localhost:27017/study_buddy
     ```
   - Replace `your-openai-api-key` with your actual OpenAI API key.
   - The MongoDB URI is pre-configured for a local MongoDB instance with a database named "study_buddy". You can customize this as follows:
     - To use a different database name: Change only the last part of the URI (e.g., `mongodb://localhost:27017/my_custom_db`).
     - To connect to a remote MongoDB instance: Replace the entire URI with your specific connection string provided by your MongoDB service.

7. Configure the `config.yaml` file:
   - Create a `config.yaml` file in the project root with the following structure:
     ```yaml
     cookie:
       expiry_days: 30
       key: your_secret_key  # Must be a string
       name: study_buddy_cookie
     credentials:
       usernames:
     ```
   - You can modify the cookie settings if desired, but the default values should work fine for most users.
   - The `credentials:` section will be automatically populated as users register.

## Usage

1. Ensure your virtual environment is activated

2. Run the application:
   ```
   streamlit run src/main.py
   ```

3. Open your web browser and go to `http://localhost:8501`

4. Register a new account or log in if you already have one

5. Use the sidebar to navigate:
   - **Home**: Get an overview of Study Buddy
   - **New Chat**: Start a new study session
   - **Chat History**: Access your previous sessions

6. To begin studying:
   1. Go to "New Chat"
   2. Upload your study materials (PDF or TXT files)
   3. Click "Upload File(s)" to process them
   4. Click "Create Assistant" to set up your AI tutor
   5. Name your study session and click "Start Chatting"

7. In the chat:
   - Ask questions about your materials
   - Your AI tutor will respond based on your uploaded content

8. Return to previous sessions anytime via "Chat History"

## Contributing

Contributions are welcome! If you have any suggestions, bug reports, or feature requests, please open an issue or submit a pull request.

## Contact

If you have any questions or inquiries, feel free to reach out to me at [oyscaleb@gmail.com](mailto:oyscaleb@gmail.com).