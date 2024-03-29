# Study Buddy

Study Buddy is an AI-powered chat application that helps students learn and study effectively by engaging with their study materials. It allows users to upload their study materials and ask questions, and the AI assistant, powered by OpenAI, provides helpful explanations and summaries based on the uploaded content.

## Features

- Upload study materials (PDF, TXT) for the AI assistant to analyze
- Interact with the AI assistant through a conversational interface to ask questions and receive answers
- Receive explanations and summaries from the uploaded study materials to enhance your understanding
- Intuitive and user-friendly interface powered by Streamlit
- Conversation history and retrieval using MongoDB for seamless continuity of learning

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/rebornify/study-buddy.git
   ```

2. Navigate to the project directory:
   ```
   cd study-buddy
   ```

3. Create a virtual environment (optional but recommended):
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

6. Set up your OpenAI API credentials:
   - Create a `.env` file in the project root directory
   - Add your OpenAI API key in the following format:
     ```
     OPENAI_API_KEY=your-api-key
     ```

7. Set up MongoDB:
   - Install MongoDB on your system or use a hosted MongoDB service
   - Update the MongoDB connection details in `main.py` if necessary

## Usage

1. Make sure you have activated the virtual environment (if you created one)

2. Run the application:
   ```
   streamlit run main.py
   ```

3. Access the application in your web browser at `http://localhost:8501`

4. Upload your study materials (PDF or TXT files) using the sidebar

5. Click the "Start Chatting" button to begin interacting with the AI assistant

6. Type your questions or messages in the input box and press Enter to send

7. The AI assistant will provide responses based on the uploaded study materials

8. Previous conversations will be displayed, allowing you to resume a conversation by clicking on the corresponding button

## Contributing

Contributions are welcome! If you have any suggestions, bug reports, or feature requests, please open an issue or submit a pull request.

## Contact

If you have any questions or inquiries, feel free to reach out to me at [oyscaleb@gmail.com](mailto:oyscaleb@gmail.com).
