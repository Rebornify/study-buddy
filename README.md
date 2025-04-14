# Study Buddy

Study Buddy is an AI-powered chat application designed to help students learn and study effectively using their own materials. It leverages OpenAI's Assistants API v2 to deliver an interactive learning experience tailored to uploaded content.

## Features

- Secure Google OAuth authentication
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

6. Set up your Google OAuth credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Navigate to "APIs & Services" > "Credentials"
   - Create an OAuth client ID (Application type: Web application)
   - Add "http://localhost:8501/oauth2callback" as an authorized redirect URI
   - Note your Client ID and Client Secret

7. Configure authentication and environment variables (for local development):
   
   A. Create a `.streamlit` directory and add the OAuth configuration:
   - Create a `.streamlit` directory in the project root if it doesn't exist:
     ```
     mkdir -p .streamlit
     ```
   - Create a `secrets.toml` file in the `.streamlit` directory with the following content:
     ```toml
     [auth]
     redirect_uri = "http://localhost:8501/oauth2callback"
     cookie_secret = "YOUR_RANDOMLY_GENERATED_SECRET"
     client_id = "YOUR_GOOGLE_CLIENT_ID"
     client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
     server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
     ```
   - Replace placeholders with your actual values:
     - `YOUR_RANDOMLY_GENERATED_SECRET`: Generate a strong, random string for securing session cookies.
     - `YOUR_GOOGLE_CLIENT_ID`: The client ID from Google Cloud Console
     - `YOUR_GOOGLE_CLIENT_SECRET`: The client secret from Google Cloud Console
   
   B. Create a `.env` file for API keys and database connection:
   - Create a `.env` file in the project root directory with the following content:
     ```
     OPENAI_API_KEY=your-openai-api-key
     MONGO_CONNECTION_STRING=mongodb://localhost:27017/study_buddy
     ```
   - Replace `your-openai-api-key` with your actual OpenAI API key.
   - The MongoDB URI is pre-configured for a local MongoDB instance with a database named "study_buddy". You can customize this as follows:
     - To use a different database name: Change only the last part of the URI (e.g., `mongodb://localhost:27017/my_custom_db`).
     - To connect to a remote MongoDB instance: Replace the entire URI with your specific connection string provided by your MongoDB service.

## Usage

1. Ensure your virtual environment is activated

2. Run the application:
   ```
   streamlit run src/main.py
   ```

3. Open your web browser and go to `http://localhost:8501`

4. Log in using your Google account

5. Use the sidebar to navigate:
   - **Home**: Get an overview of Study Buddy
   - **New Study Session**: Start a new study session
   - **Previous Sessions**: Access your previous sessions

6. To begin studying:
   1. Go to "New Study Session"
   2. Upload your study materials (PDF or TXT files) or select from previously uploaded files
   3. Click "Upload File(s)" to process new materials
   4. Provide a descriptive name for your collection of study materials (e.g., 'Chapter 5 Notes') and click 'Create Collection'.
      - The system automatically detects if an identical set of files has been previously uploaded and reuses the existing collection to optimize resource usage.
      - An AI assistant, specifically configured for this collection of materials, will be automatically created or retrieved.
   5. Enter a title for your study session and click "Start Session"

7. In the chat:
   - Ask questions about your materials
   - Your AI tutor will respond based on your uploaded content
   - You can see which study materials are being used in the current session

8. Return to previous sessions anytime via "Previous Sessions"

## Resource Management

To optimize performance and minimize costs, Study Buddy efficiently manages OpenAI resources:

- **Files**: Once uploaded, files are stored and can be reused across multiple collections
- **Collections**: If an identical set of files is uploaded again, the existing vector store (collection) is reused, avoiding redundant processing and storage
- **Assistants**: Each unique collection of materials is automatically paired with a dedicated AI assistant instance. This ensures the AI's context is specific to the relevant materials and avoids manual configuration

This resource management strategy optimizes OpenAI API usage and costs while allowing users to easily create distinct study sessions tailored to different sets of materials.

## Contributing

Contributions are welcome! If you have any suggestions, bug reports, or feature requests, please open an issue or submit a pull request.

## Contact

If you have any questions or inquiries, feel free to reach out to me at [oyscaleb@gmail.com](mailto:oyscaleb@gmail.com).