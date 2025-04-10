# Zoom Transcription API with Real-time Audio Processing

A system for real-time transcription of Zoom meetings with AI-powered recommendations and Zoom chat integration.

## Features

- **Real-time Transcription**: Captures and transcribes Zoom meeting audio in real-time
- **Gemini AI Integration**: Uses Google's Gemini API for accurate transcription
- **Zoom Chat Integration**: Automatically sends transcriptions to Zoom chat
- **RAG Recommendations**: Generates context-aware recommendations using vector search
- **Client-Server Architecture**: Flexible deployment with separate client and server components
- **WebSocket Communication**: Low-latency, bidirectional data transfer

## System Architecture

The system consists of:

1. **Server**: FastAPI application that processes audio and generates transcriptions
2. **Client**: Python application that captures system audio and communicates with the server
3. **Knowledge Base**: Text documents for generating context-aware recommendations
4. **Zoom Integration**: APIs for sending transcriptions to Zoom chat

## Setup and Installation

### Server Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/zoom-transcription.git
   cd zoom-transcription
   ```

2. **Install server dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file and add your API keys:
   - `GEMINI_API_KEY`: Google Gemini API key
   - `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, `ZOOM_ACCOUNT_ID`: Zoom API credentials

4. **Start the server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Client Setup

1. **Install client dependencies**:
   ```bash
   cd client
   pip install -r requirements.txt
   ```

2. **Run the client**:
   ```bash
   python zoom_transcriber_client.py
   ```

   Options:
   - `--server`: Server URL (default: ws://localhost:8000)
   - `--meeting-id`: Custom meeting ID (default: auto-generated)
   - `--duration`: Audio chunk duration in seconds (default: 5)

## Usage Workflow

1. **Start the server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Start a Zoom meeting** on your computer

3. **Run the client application**:
   ```bash
   python client/zoom_transcriber_client.py
   ```

4. **View transcriptions**:
   - Real-time transcriptions appear in the client terminal
   - Transcriptions are sent to the configured Zoom chat channel
   - Transcriptions are saved to a local file when the client exits

## Data Setup

The `Data/` directory contains knowledge base documents for the recommendation system. Each file should:

- Be in `.txt` format
- Have the service name as the filename (e.g., `cloud_services.txt`)
- Have the first paragraph as a short description
- Include detailed information in subsequent paragraphs

Example:
```
Cloud Hosting Service

Our enterprise-grade cloud hosting provides scalable infrastructure with 99.9% uptime guarantee.

Features include auto-scaling, load balancing, dedicated support, and comprehensive security...
```

## API Endpoints

- **WebSocket**: `/ws/transcribe/{meeting_id}` - Real-time audio transcription
- **POST**: `/transcribe` - Upload and transcribe audio files
- **GET**: `/status/{meeting_id}` - Check transcription status
- **GET**: `/health` - Server health check

## Configuration Options

Edit the `.env` file to configure:

- API keys and credentials
- Zoom integration settings
- Audio capture parameters
- Recommendation system settings

## Requirements

### Server Requirements
- Python 3.9+
- FastAPI
- Google Generative AI (Gemini)
- soundcard
- numpy
- Other dependencies in `requirements.txt`

### Client Requirements
- Python 3.9+
- websockets
- soundcard
- numpy

## Zoom API Setup

1. Create a Zoom App on the [Zoom Marketplace](https://marketplace.zoom.us/)
2. Use "Server-to-Server OAuth" app type
3. Add the "Chat Message" and "IM Chat" scopes
4. Generate credentials and add them to the `.env` file

## Troubleshooting

### Audio Capture Issues
- Ensure system audio drivers are up to date
- Check that the soundcard library can access your audio devices
- Try running the client with elevated permissions if needed

### Connection Issues
- Verify server and client are on the same network or accessible
- Check firewall settings for WebSocket connections
- Ensure port 8000 is open on the server

### Transcription Quality
- Adjust audio capture settings for better quality
- Check microphone or system audio levels
- Try different audio chunk durations

## License

This project is intended for educational and research purposes.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 