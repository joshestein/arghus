import asyncio
import os
from contextlib import asynccontextmanager

import ngrok
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

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
    twilio_phone = client.incoming_phone_numbers(TWILIO_NUMBER_SID).update(
        voice_url=listener.url() + "/gather"
    )

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


@app.api_route("/gather", methods=["GET", "POST"])
def gather():
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/voice")
    gather.say("Thanks for calling")
    response.append(gather)

    # if caller fails to select an option, redirect them into a loop
    response.redirect("/gather")
    return HTMLResponse(content=str(response), media_type="application/xml")


if __name__ == "__main__":
    uvicorn.run(
        "twilio_voice:app", host="127.0.0.1", port=PORT, reload=True, log_level="debug"
    )
