from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv
import asyncio
import queue
import threading
from typing import Optional
import json
from datetime import datetime
import soundcard as sc
import numpy as np
import wave
import io
import base64

# Load environment variables
load_dotenv()

# Configure Gemini API and pre-load model
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
transcription_model = genai.GenerativeModel("gemini-2.0-flash-001")

app = FastAPI(title="Zoom Transcription API",
             description="API for transcribing Zoom meetings and generating recommendations",
             version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global queues for processing
transcription_queue = queue.Queue()
recommendation_queue = queue.Queue()

# Add audio capture configuration
AUDIO_CHUNK_SIZE = 1024
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_FORMAT = np.int16

class TranscriptionRequest(BaseModel):
    meeting_id: str
    user_id: str
    auto_send_to_zoom: bool = False
    audio_data: Optional[bytes] = None  # Base64 encoded audio data

class TranscriptionResponse(BaseModel):
    meeting_id: str
    transcription: str
    timestamp: str
    status: str

# Initialize audio capture with lazy loading
class AudioCapture:
    def __init__(self):
        self.is_running = False
        self.recording_thread = None
        self.audio_queue = queue.Queue()
        self.current_meeting_id = None
        self._speaker = None
        
    def _get_speaker(self):
        if self._speaker is None:
            self._speaker = sc.default_speaker()
        return self._speaker
        
    def start_capture(self, meeting_id: str):
        if self.is_running:
            return False
            
        self.is_running = True
        self.current_meeting_id = meeting_id
        self.recording_thread = threading.Thread(target=self._capture_audio)
        self.recording_thread.start()
        return True
        
    def stop_capture(self):
        self.is_running = False
        if self.recording_thread:
            self.recording_thread.join()
        self.current_meeting_id = None
        
    def _capture_audio(self):
        try:
            speaker = self._get_speaker()
            
            # Create a recorder
            with speaker.recorder(samplerate=AUDIO_SAMPLE_RATE, 
                                channels=AUDIO_CHANNELS) as recorder:
                while self.is_running:
                    # Record a chunk of audio
                    audio_data = recorder.record(numframes=AUDIO_CHUNK_SIZE)
                    
                    # Convert to bytes
                    audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                    
                    # Add to queue for processing
                    self.audio_queue.put({
                        "meeting_id": self.current_meeting_id,
                        "audio_data": audio_bytes,
                        "timestamp": datetime.now().isoformat()
                    })
                    
        except Exception as e:
            print(f"Error in audio capture: {e}")
            self.is_running = False

# Initialize audio capture
audio_capture = AudioCapture()

# Background task for processing transcriptions
async def process_transcription(audio_file_path: str, meeting_id: str):
    try:
        # Transcribe using Gemini
        with open(audio_file_path, "rb") as f:
            audio_data = f.read()
            
        content = [
            {"text": "Transcribe the following audio precisely. Just return the transcription text with no additional commentary."},
            {
                "inline_data": {
                    "mime_type": "audio/wav",
                    "data": audio_data
                }
            }
        ]
        
        response = transcription_model.generate_content(content)
        transcription = response.text.strip()
        
        # Add to recommendation queue
        recommendation_queue.put({
            "meeting_id": meeting_id,
            "transcription": transcription,
            "timestamp": datetime.now().isoformat()
        })
        
        return transcription
        
    except Exception as e:
        print(f"Error in transcription: {e}")
        return None

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meeting_id: str = None,
    user_id: str = None,
    auto_send_to_zoom: bool = False
):
    if not file.filename.endswith('.wav'):
        raise HTTPException(status_code=400, detail="Only WAV files are supported")
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
            
        # Process transcription in background
        transcription = await process_transcription(temp_file_path, meeting_id)
        
        # Clean up
        os.unlink(temp_file_path)
        
        if not transcription:
            raise HTTPException(status_code=500, detail="Transcription failed")
            
        return TranscriptionResponse(
            meeting_id=meeting_id,
            transcription=transcription,
            timestamp=datetime.now().isoformat(),
            status="success"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{meeting_id}")
async def get_transcription_status(meeting_id: str):
    # TODO: Implement status tracking
    return {"status": "processing", "meeting_id": meeting_id}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

class AudioStream:
    def __init__(self):
        self.streams = {}  # meeting_id -> audio buffer
        
    def add_audio_chunk(self, meeting_id: str, audio_data: bytes):
        if meeting_id not in self.streams:
            self.streams[meeting_id] = []
        self.streams[meeting_id].append(audio_data)
        
    def get_audio_chunk(self, meeting_id: str):
        if meeting_id in self.streams and self.streams[meeting_id]:
            return self.streams[meeting_id].pop(0)
        return None
        
    def clear_stream(self, meeting_id: str):
        if meeting_id in self.streams:
            del self.streams[meeting_id]

# Initialize audio stream manager
audio_stream = AudioStream()

@app.websocket("/ws/transcribe/{meeting_id}")
async def websocket_transcribe(websocket: WebSocket, meeting_id: str):
    await websocket.accept()
    
    try:
        while True:
            # Receive audio data from client
            data = await websocket.receive_json()
            
            if "audio_data" in data:
                # Add audio chunk to stream
                audio_data = base64.b64decode(data["audio_data"])
                audio_stream.add_audio_chunk(meeting_id, audio_data)
                
                # Process audio chunk
                transcription = await process_audio_chunk(audio_data, meeting_id)
                
                if transcription:
                    # Send transcription to client
                    await websocket.send_json({
                        "meeting_id": meeting_id,
                        "transcription": transcription,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Send transcription to Zoom chat
                    try:
                        channel_id = get_zoom_channel_id(os.getenv("ZOOM_CHANNEL_NAME", "Meeting Recommendations"))
                        if channel_id:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            zoom_message = f"[{timestamp}] Transcription:\n{transcription}"
                            send_zoom_message(channel_id, zoom_message)
                    except Exception as e:
                        print(f"Error sending to Zoom: {e}")
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        audio_stream.clear_stream(meeting_id)
        await websocket.close()

# Optimize process_audio_chunk to use pre-loaded model
async def process_audio_chunk(audio_data: bytes, meeting_id: str):
    try:
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            # Write WAV header
            with wave.open(temp_file, 'wb') as wav_file:
                wav_file.setnchannels(AUDIO_CHANNELS)
                wav_file.setsampwidth(2)  # 16-bit audio
                wav_file.setframerate(AUDIO_SAMPLE_RATE)
                wav_file.writeframes(audio_data)
            
            temp_file_path = temp_file.name
            
        # Use pre-loaded model for transcription
        with open(temp_file_path, "rb") as f:
            audio_data = f.read()
            
        content = [
            {"text": "Transcribe the following audio precisely. Just return the transcription text with no additional commentary."},
            {
                "inline_data": {
                    "mime_type": "audio/wav",
                    "data": audio_data
                }
            }
        ]
        
        response = transcription_model.generate_content(content)
        transcription = response.text.strip()
        
        # Clean up
        os.unlink(temp_file_path)
        
        return transcription
        
    except Exception as e:
        print(f"Error processing audio chunk: {e}")
        return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 