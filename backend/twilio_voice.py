import asyncio
import os
from contextlib import asynccontextmanager

import ngrok
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from twilio.rest import Client

load_dotenv()
TWILIO_API_SID = os.getenv("TWILIO_API_SID")
TWILIO_SECRET_KEY = os.getenv("TWILIO_SECRET_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_NUMBER_SID = os.getenv("TWILIO_NUMBER_SID")
client = Client(TWILIO_API_SID, TWILIO_SECRET_KEY, TWILIO_ACCOUNT_SID)

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN")

PORT = int(os.getenv("PORT", "8080"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code here
    print("Setting up ngrok tunnel...")
    listener = await ngrok.forward(
        addr=PORT,
        proto="http",
        authtoken=NGROK_AUTH_TOKEN,
        domain=NGROK_DOMAIN,
    )
    print(listener.url())

    try:
        yield
    except asyncio.CancelledError:
        print("Lifespan cancelled")
    except KeyboardInterrupt:
        print("Lifespan interrupted by keyboard")
    finally:
        print("Closing ngrok tunnel...")
        ngrok.disconnect()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello World"}


if __name__ == "__main__":
    uvicorn.run(
        "twilio_voice:app", host="127.0.0.1", port=PORT, reload=True, log_level="debug"
    )
