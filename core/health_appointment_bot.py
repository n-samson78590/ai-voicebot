#!/usr/bin/env python3
"""
OpenAI Realtime Health Appointment Bot - Enhanced Production Version
Bridges Exotel WebSocket with OpenAI Realtime API for appointment booking
Multi-Sample Rate Support: 8kHz, 16kHz, 24kHz with variable chunk sizes
"""

import asyncio
import websockets
import json
import logging
import base64
import time
import struct
import ssl
import os
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import Config
from services_config import ServicesConfig

# Configure enhanced logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper()),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


class HealthAppointmentBot:
    """Health appointment booking bot using OpenAI Realtime API"""
    
    def __init__(self):
        # Validate configuration
        Config.validate()
        
        self.exotel_connections: Dict[str, Dict[str, Any]] = {}
        self.openai_connections: Dict[str, Any] = {}
        self.openai_connecting = set()
        
        # Audio buffering with dynamic sample rate support
        self.audio_buffers: Dict[str, bytes] = {}
        self.connection_sample_rates: Dict[str, int] = {}
        self.connection_chunk_sizes: Dict[str, int] = {}
        
        # Default audio configuration
        self.default_sample_rate = Config.DEFAULT_SAMPLE_RATE
        self.min_chunk_size_ms = Config.MIN_CHUNK_SIZE_MS
        self.buffer_size_ms = Config.BUFFER_SIZE_MS
        
        # OpenAI Configuration
        self.openai_api_key = Config.OPENAI_API_KEY
        self.openai_model = Config.OPENAI_MODEL
        self.openai_voice = Config.OPENAI_VOICE
        
        # Enhanced features flags
        self.exotel_enhanced_events = Config.EXOTEL_MARK_CLEAR_ENHANCED
        self.variable_chunk_support = Config.EXOTEL_VARIABLE_CHUNK_SUPPORT
        self.dynamic_chunk_sizing = Config.DYNAMIC_CHUNK_SIZING
        
        # Get health services
        self.services = ServicesConfig.get_services("health")
        
        logger.info("Enhanced OpenAI Realtime Health Appointment Bot initialized!")
        logger.info(f"Multi-sample rate support: {Config.SUPPORTED_SAMPLE_RATES} Hz")
        logger.info(f"Variable chunk sizes: {self.min_chunk_size_ms}ms - {Config.MAX_CHUNK_SIZE_MS}ms")
        logger.info(f"Enhanced Exotel events: {self.exotel_enhanced_events}")
        logger.info(f"Company: {Config.COMPANY_NAME}")
        logger.info(f"Appointment Bot: {Config.HEALTH_BOT_NAME}")

    async def handle_exotel_websocket(self, websocket, path=None):
        """Handle incoming WebSocket connection from Exotel"""
        stream_id = "unknown"
        
        try:
            # Extract sample rate from WebSocket path if available
            # Handle different websockets versions - path might be in websocket.path or passed as parameter
            try:
                websocket_path = path or getattr(websocket, 'path', '/')
            except:
                websocket_path = '/'
            
            detected_sample_rate = self._extract_sample_rate_from_websocket_path(websocket_path)
            logger.info(f"NEW APPOINTMENT BOOKING CALL: {websocket.remote_address}")
            logger.info(f"Detected sample rate: {detected_sample_rate}Hz")
            
            # Set up connection keep-alive and error handling
            async for message in websocket:
                try:
                    logger.info(f"EXOTEL MESSAGE: {message}")
                    data = json.loads(message)
                    event = data.get("event", "")
                    
                    # Extract stream ID
                    if "streamSid" in data:
                        stream_id = data["streamSid"]
                    elif "stream_sid" in data:
                        stream_id = data["stream_sid"]

                    # Detect sample rate from event
                    event_sample_rate = self._extract_sample_rate_from_event(data)
                    if event_sample_rate is not None and event_sample_rate != detected_sample_rate:
                        detected_sample_rate = event_sample_rate
                    
                    # Initialize connection settings on first event
                    if stream_id not in self.connection_sample_rates:
                        self._initialize_connection_settings(stream_id, detected_sample_rate, data)
                    
                    logger.info(f"EVENT: '{event}' for {stream_id}")
                    
                    # Store Exotel connection
                    if stream_id not in self.exotel_connections:
                        self.exotel_connections[stream_id] = {
                            "websocket": websocket,
                            "start_time": time.time(),
                            "openai_connected": False,
                            "sample_rate": self.connection_sample_rates.get(stream_id, detected_sample_rate),
                            "chunk_size_bytes": self.connection_chunk_sizes.get(stream_id, 0),
                        }
                    
                    # Handle events
                    if event == "connected":
                        await self.handle_exotel_connected(stream_id, data)
                    elif event == "start":
                        await self.handle_exotel_start(stream_id, data)
                    elif event == "media":
                        await self.handle_exotel_media(stream_id, data)
                    elif event == "mark":
                        await self.handle_exotel_mark(stream_id, data)
                    elif event == "clear":
                        await self.handle_exotel_clear(stream_id, data)
                    elif event == "stop":
                        await self.handle_exotel_stop(stream_id, data)
                        break
                    else:
                        logger.debug(f"Unhandled event: {event}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed: {stream_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self.cleanup_connections(stream_id)


    def _extract_sample_rate_from_websocket_path(self, websocket_path: str) -> int:
        """Extract sample rate from websocket query params"""
        try:
            parsed = urlparse(websocket_path or "/")
            query_params = parse_qs(parsed.query)
            for key in ("sample-rate", "sample_rate", "samplerate"):
                if key in query_params:
                    rate = int(query_params[key][0])
                    if rate in Config.SUPPORTED_SAMPLE_RATES:
                        return rate
        except Exception as e:
            logger.warning(f"Failed to parse sample rate: {e}")
        return self.default_sample_rate


    def _extract_sample_rate_from_event(self, data: dict) -> Optional[int]:
        """Extract sample rate from Exotel event payload"""
        if not isinstance(data, dict):
            return None
        
        candidate_values = []
        media_format = data.get("mediaFormat") or {}
        if isinstance(media_format, dict):
            candidate_values.extend([
                media_format.get("sampleRate"),
                media_format.get("sample_rate"),
            ])
        
        candidate_values.extend([
            data.get("sampleRate"),
            data.get("sample_rate"),
        ])
        
        for value in candidate_values:
            if value is not None:
                try:
                    rate = int(value)
                    if rate in Config.SUPPORTED_SAMPLE_RATES:
                        return rate
                except (TypeError, ValueError):
                    pass
        
        return None


    def _initialize_connection_settings(self, stream_id: str, sample_rate: int, start_data: dict):
        """Initialize connection settings based on detected parameters"""
        self.connection_sample_rates[stream_id] = sample_rate
        
        if self.dynamic_chunk_sizing:
            chunk_size_ms = Config.get_adaptive_chunk_size(sample_rate)
        else:
            chunk_size_ms = self.min_chunk_size_ms
        
        chunk_size_bytes = Config.get_chunk_size_bytes(sample_rate, chunk_size_ms)
        self.connection_chunk_sizes[stream_id] = chunk_size_bytes
        
        logger.info(f"Connection initialized: {sample_rate}Hz, {chunk_size_ms}ms chunks")


    async def handle_exotel_connected(self, stream_id: str, data: dict):
        """Handle Exotel connected event"""
        logger.info(f"Exotel connected: {stream_id}")
        if stream_id != "unknown":
            await self.ensure_openai_connected(stream_id)


    async def handle_exotel_start(self, stream_id: str, data: dict):
        """Handle Exotel start event"""
        sample_rate = self.connection_sample_rates.get(stream_id, self.default_sample_rate)
        logger.info(f"Appointment bot call started: {stream_id} @ {sample_rate}Hz")
        await self.ensure_openai_connected(stream_id)


    async def handle_exotel_media(self, stream_id: str, data: dict):
        """Handle incoming audio from Exotel"""
        if stream_id not in self.openai_connections:
            logger.warning(f"OpenAI connection not ready for {stream_id}; connecting now")
            await self.ensure_openai_connected(stream_id)

        await asyncio.sleep(0.1) # Small delay to allow connection to establish

        if stream_id not in self.openai_connections:
            logger.error(f"Failed to establish OpenAI connection for {stream_id}")
            return
        
        if stream_id in self.openai_connections:
            media = data.get("media", {})
            audio_payload = media.get("payload", "")

            try:
                payload = media.get("payload", "")
                if payload:
                    audio_data = base64.b64decode(payload)
                    
                    if stream_id not in self.audio_buffers:
                        self.audio_buffers[stream_id] = b""
                    
                    self.audio_buffers[stream_id] += audio_data
                    
                    # Process variable chunks
                    sample_rate = self.connection_sample_rates.get(stream_id, self.default_sample_rate)
                    await self._process_variable_chunks(stream_id, sample_rate)
                    
            except Exception as e:
                logger.error(f"Error processing media: {e}")


    async def _process_variable_chunks(self, stream_id: str, sample_rate: int):
        """Process audio with variable chunk sizes"""
        min_chunk_bytes = Config.get_chunk_size_bytes(sample_rate, self.min_chunk_size_ms)
        buffer = self.audio_buffers[stream_id]
        
        while len(buffer) >= min_chunk_bytes:
            chunk = buffer[:min_chunk_bytes]
            self.audio_buffers[stream_id] = buffer[min_chunk_bytes:]
            await self._send_audio_to_openai(stream_id, chunk, sample_rate)
            buffer = self.audio_buffers[stream_id]


    async def _send_audio_to_openai(self, stream_id: str, chunk: bytes, sample_rate: int):
        """Send audio chunk to OpenAI"""
        try:
            if stream_id in self.openai_connections:
                openai_ws = self.openai_connections[stream_id]["websocket"]
                audio_base64 = base64.b64encode(chunk).decode('utf-8')
                
                message = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_base64
                }
                await openai_ws.send(json.dumps(message))
                logger.debug(f"Sent {len(chunk)} bytes to OpenAI for {stream_id}")
                
        except Exception as e:
            logger.error(f"Error sending to OpenAI: {e}")


    async def ensure_openai_connected(self, stream_id: str):
        """Start the OpenAI connection once for the real Exotel stream id."""
        if stream_id == "unknown":
            logger.info("Deferring OpenAI connection until Exotel provides streamSid")
            return
        if stream_id in self.openai_connections or stream_id in self.openai_connecting:
            return

        self.openai_connecting.add(stream_id)
        try:
            await self.connect_to_openai(stream_id)
        finally:
            self.openai_connecting.discard(stream_id)


    async def handle_exotel_mark(self, stream_id: str, data: dict):
        """Handle Exotel mark event"""
        mark_name = data.get("mark", {}).get("name", "unknown")
        logger.info(f"Mark: {mark_name}")


    async def handle_exotel_clear(self, stream_id: str, data: dict):
        """Handle Exotel clear event (interruption)"""
        logger.info(f"Clear signal received")
        if stream_id in self.openai_connections:
            await self._commit_audio_buffer(stream_id)


    async def _commit_audio_buffer(self, stream_id: str):
        """Commit remaining audio buffer"""
        if stream_id in self.audio_buffers and len(self.audio_buffers[stream_id]) > 0:
            sample_rate = self.connection_sample_rates.get(stream_id, self.default_sample_rate)
            await self._send_audio_to_openai(stream_id, self.audio_buffers[stream_id], sample_rate)
            self.audio_buffers[stream_id] = b""


    async def handle_exotel_stop(self, stream_id: str, data: dict):
        """Handle Exotel stop event"""
        logger.info(f"Appointment bot call ended: {stream_id}")


    async def connect_to_openai(self, stream_id: str):
        """Establish connection to OpenAI Realtime API"""
        try:
            sample_rate = self.connection_sample_rates.get(stream_id, self.default_sample_rate)
            logger.info(f"CONNECTING TO OPENAI for {stream_id} @ {sample_rate}Hz")
            
            # URL for latest OpenAI Realtime API
            url = f"wss://api.openai.com/v1/realtime?model={self.openai_model}"
            
            # Create SSL context that handles certificate verification
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Realtime GA no longer uses the OpenAI-Beta header
            headers = [
                ("Authorization", f"Bearer {self.openai_api_key}")
            ]
            
            # Connect to OpenAI Realtime API with GA format
            openai_ws = await websockets.connect(
                url,
                extra_headers=headers,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            # Get GA session configuration
            session_config = Config.get_enhanced_session_config(sample_rate, self.openai_voice)
            session_config['instructions'] = self._get_appointment_instructions()
            session_config['tools'] = [
                {
                    "type": "function",
                    "name": "book_appointment",
                    "description": "Book a hospital appointment for the patient",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_name": {"type": "string", "description": "Full name of patient"},
                            "appointment_type": {"type": "string", "description": "Type of appointment (General Consultation, Specialized Consultation, Follow-up)"},
                            "preferred_date": {"type": "string", "description": "Preferred date (DD-MM-YYYY)"},
                            "preferred_time": {"type": "string", "description": "Preferred time (HH:MM)"},
                            "contact_phone": {"type": "string", "description": "Patient contact number"},
                            "medical_history": {"type": "string", "description": "Brief medical history or reason for visit"}
                        },
                        "required": ["patient_name", "appointment_type", "preferred_date", "contact_phone"]
                    }
                }
            ]
            
            session_config["input_audio_format"] = self._get_realtime_audio_format(session_config, "input")
            session_config["output_audio_format"] = self._get_realtime_audio_format(session_config, "output")
            session_config["voice"] = session_config.get("audio", {}).get("output", {}).get("voice", self.openai_voice)
            
            self.openai_connections[stream_id] = {
                "websocket": openai_ws,
                "start_time": time.time(),
                "sample_rate": sample_rate,
                "input_format": self._get_realtime_audio_format(session_config, "input"),
                "output_format": self._get_realtime_audio_format(session_config, "output"),
                "session_config": session_config,
                "session_ready": False,
                "greeting_sent": False,
            }
            
            logger.info(f"OpenAI Realtime CONNECTED for {stream_id} @ {sample_rate}Hz")
            logger.info(f"Audio Format: {session_config['input_audio_format']} → {session_config['output_audio_format']}")
            
            # Start listening before session.update so errors/session.updated/audio are not missed.
            asyncio.create_task(self.handle_openai_responses(stream_id, openai_ws))

            # Configure GA OpenAI session. The greeting is sent after session.updated.
            await self.configure_openai_session(stream_id)
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            if "SSL" in str(e):
                logger.error("SSL Error - check certificate")
            elif "authentication" in str(e).lower():
                logger.error("Authentication Error: Check OpenAI API key")
            elif "websocket" in str(e).lower():
                logger.error("WebSocket Error: Check connection and headers")


    def _get_appointment_instructions(self) -> str:
        """Get appointment booking instructions for the bot"""
        services = "\n".join([f"  - {s['name']} ({s['duration']})" for s in self.services])
        
        return f"""
        You are a helpful hospital appointment booking assistant for {Config.COMPANY_NAME} and you want to be able to schedule an appointment.

        Your goals:
        1. Greet the user warmly
        2. Understand their healthcare needs
        3. Recommend appropriate appointment type
        4. Collect necessary information
        5. Confirm appointment details

        Available Services:
        {services}

        Process:
        - Ask about their health concern
        - Categorise concern into whether it requires a general consultation, specialized consultation, or follow-up
        - Suggest appropriate appointment type
        - Clarify if appointment is for self or someone else
        - Collect: full name of caller if appointment is for self else full name of patient, preferred date/time, contact number, medical history
        - Confirm all details
        - Thank them for booking

        Be professional, compassionate, and efficient. Always confirm the full appointment details before ending the call."""

    def _get_realtime_audio_format(self, session_config: dict, direction: str) -> str:
        """Return the GA Realtime audio format type for input or output."""
        audio_config = session_config.get("audio", {}).get(direction, {})
        format_config = audio_config.get("format", {})
        if isinstance(format_config, dict):
            return format_config.get("type", "audio/pcmu")
        return format_config or "audio/pcmu"


    def _realtime_session_payload(self, session_config: dict) -> dict:
        """Remove local logging aliases before sending GA session config."""
        payload = dict(session_config)
        payload.pop("model", None)
        payload.pop("input_audio_format", None)
        payload.pop("output_audio_format", None)
        payload.pop("voice", None)
        payload.pop("temperature", None)  # Removed in GA API
        return payload


    async def configure_openai_session(self, stream_id: str):
        """Configure OpenAI Realtime session"""
        try:
            openai_connection = self.openai_connections[stream_id]
            openai_ws = openai_connection["websocket"]
            session_config = openai_connection["session_config"]
            sample_rate = openai_connection["sample_rate"]
            
            # Send GA session configuration
            session_update = {
                "type": "session.update",
                "session": self._realtime_session_payload(session_config)
            }
            
            await openai_ws.send(json.dumps(session_update))
            logger.info(f"GA OPENAI SESSION CONFIGURED for {stream_id}")
            logger.info(f"Sample Rate: {sample_rate}Hz")
            logger.info(f"Input Format: {session_config['input_audio_format']}")
            logger.info(f"Output Format: {session_config['output_audio_format']}")
            logger.info(f"Voice: {session_config['voice']}")
            
        except Exception as e:
            logger.error(f"Error configuring GA OpenAI session: {e}")


    async def send_initial_greeting(self, stream_id: str):
        """Send initial greeting to caller"""
        try:
            openai_connection = self.openai_connections[stream_id]
            openai_ws = openai_connection["websocket"]
            sample_rate = openai_connection["sample_rate"]
            
            # Create conversation item with greeting
            greeting_msg = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": f"A patient just called for appointment booking. The connection is running at {sample_rate}Hz audio quality. \
                        Please greet them warmly and ask how you can help them today."
                    }]
                }
            }
            await openai_ws.send(json.dumps(greeting_msg))
            
            # Trigger response with correct parameters (output_modalities, not modalities)
            response_msg = {
                "type": "response.create",
                "response": {
                    "output_modalities": ["audio"],
                    "instructions": "Give a warm, professional greeting, asking the user how you can assist them with their appointment booking. \
                    Keep it concise and natural."
                }
            }
            await openai_ws.send(json.dumps(response_msg))
            
            openai_connection["greeting_sent"] = True
            logger.info(f"Initial greeting sent for {stream_id} @ {sample_rate}Hz")
            
        except Exception as e:
            logger.error(f"Error sending greeting: {e}")


    async def handle_openai_responses(self, stream_id: str, openai_ws):
        """Handle responses from OpenAI with real-time logging"""
        try:
            async for message in openai_ws:
                try:
                    data = json.loads(message)
                    event_type = data.get("type", "")

                    logger.debug(f"ENHANCED OPENAI EVENT: {event_type} for {stream_id}")

                    if event_type in ("response.audio.delta", "response.output_audio.delta"):
                        await self._handle_audio_delta(stream_id, data)
                    
                    elif event_type in ("response.output_audio_transcript.delta", "response.audio_transcript.delta"):
                        transcript_delta = data.get('delta', '')
                        if transcript_delta.strip():
                            logger.info(f"BOT SPEAKING: {transcript_delta}")
                    
                    elif event_type == "response.function_call_arguments.done":
                        await self._handle_function_call(stream_id, data)
                    
                    elif event_type == "input_audio_buffer.speech_started":
                        logger.info(f"Caller started speaking for {stream_id}")
                    
                    elif event_type == "input_audio_buffer.speech_stopped":
                        logger.info(f"Caller stopped speaking for {stream_id}")
                    
                    elif event_type == "response.done":
                        logger.info(f"Bot response completed for {stream_id}")
                    
                    elif event_type == "session.updated":
                        logger.info(f"Session updated for {stream_id}")
                        if stream_id in self.openai_connections:
                            self.openai_connections[stream_id]["session_ready"] = True
                            if not self.openai_connections[stream_id].get("greeting_sent"):
                                await self.send_initial_greeting(stream_id)
                    
                    elif event_type == "error":
                        logger.error(f"OpenAI error: {data}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error from OpenAI: {e}")
                except Exception as e:
                    logger.error(f"Error processing OpenAI response: {e}")
                    
        except Exception as e:
            logger.error(f"Error in OpenAI response handler: {e}")


    async def _handle_audio_delta (self, stream_id: str, data: dict): # handle_exotel_connected
        """Handle audio delta from OpenAI"""
        try:
            audio_data = data.get("delta", "")
            if audio_data:
                audio_bytes = base64.b64decode(audio_data)
                logger.info(f"AUDIO DELTA RECEIVED: {len(audio_bytes)} bytes")
                
                # Send to Exotel
                if stream_id in self.exotel_connections:
                    exotel_ws = self.exotel_connections[stream_id]["websocket"]
                    
                    media_msg = {
                        "event": "media",
                        "streamSid": stream_id,
                        "media": {
                            "payload": base64.b64encode(audio_bytes).decode('utf-8')
                        }
                    }
                    await exotel_ws.send(json.dumps(media_msg))
                    logger.info(f"SENT AUDIO TO EXOTEL: {len(audio_bytes)} bytes")
                    
        except Exception as e:
            logger.error(f"Error handling audio delta: {e}")


    async def _handle_function_call(self, stream_id: str, data: dict):
        """Handle function calls from OpenAI"""
        try:
            call_id = data.get("call_id")
            function_name = data.get("name", "")
            arguments_str = data.get("arguments", "{}")
            
            logger.info(f"Function call: {function_name}")
            
            if function_name == "book_appointment":
                args = json.loads(arguments_str)
                result = await self.book_appointment(args)
                
                # Send result back
                if stream_id in self.openai_connections:
                    openai_ws = self.openai_connections[stream_id]["websocket"]
                    
                    result_msg = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_result",
                            "call_id": call_id,
                            "result": json.dumps(result)
                        }
                    }
                    await openai_ws.send(json.dumps(result_msg))
                    
                    logger.info(f"Appointment booking processed")
                    
        except Exception as e:
            logger.error(f"Error handling function call: {e}")


    async def book_appointment(self, args: dict) -> dict:
        """Process appointment booking"""
        logger.info(f"Booking appointment: {args.get('patient_name')}")
        
        return {
            "status": "success",
            "message": f"Appointment confirmed for {args.get('patient_name')}",
            "appointment_id": f"APT_{int(time.time())}",
            "patient_name": args.get('patient_name'),
            "appointment_type": args.get('appointment_type'),
            "date": args.get('preferred_date'),
            "time": args.get('preferred_time'),
            "contact": args.get('contact_phone'),
            "booking_time": time.strftime('%Y-%m-%d %H:%M:%S')
        }


    async def start_server(self):
        """Start the WebSocket server"""
        try:
            logger.info(f"Health Appointment Bot starting on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
            logger.info("Ready for Exotel streaming connections")
            
            async with websockets.serve(
                self.handle_exotel_websocket,
                Config.SERVER_HOST,
                Config.SERVER_PORT
            ):
                logger.info(f'Health appointment bot server running at ws://{Config.SERVER_HOST}:{Config.SERVER_PORT}')
                await asyncio.Future()  # Run forever
                
        except Exception as e:
            logger.error(f'Server Error: {e}')
            raise


    async def cleanup_connections(self, stream_id: str):
        """Clean up connections"""
        try:
            if stream_id in self.openai_connections:
                openai_ws = self.openai_connections[stream_id]["websocket"]
                if not openai_ws.closed:
                    await openai_ws.close()
                del self.openai_connections[stream_id]
                logger.info (f"Cleaned up OpenAI connection for {stream_id}")
            
            if stream_id in self.exotel_connections:
                del self.exotel_connections[stream_id]
                logger.info(f"Cleaned up Exotel connection for {stream_id}")
            
            if stream_id in self.audio_buffers:
                del self.audio_buffers[stream_id]
                logger.info(f"Cleared audio buffer for {stream_id}")
            
            if stream_id in self.connection_sample_rates:
                del self.connection_sample_rates[stream_id]
                logger.info(f"Cleared sample rate config for {stream_id}")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Start the Health Appointment Bot"""
    try:
        bot = HealthAppointmentBot()
        await bot.start_server()
    except Exception as e:
        logger.error(f'Error: {e}')
        raise


if __name__ == "__main__":
    asyncio.run(main())
