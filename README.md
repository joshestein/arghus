# Arghus

## Why

I am worried about the breakdown of trust between people. As generative AI gets
better we are no longer able to discern truth from reality. I think trust and
authenticity are part of the fabric of connection and meaning.

The current state of deepfakes is excellent. Progress is improving. My defense
is against deepfake-driven scams.

Consider:

Someone clones your voice. They find your mom's number. They call her,
pretending to be you. Your mom can't tell the difference. 'You' are panicked,
extremely emotional. You've been mugged and all your things have been taken.
You don't have a wallet, a phone, anything. Your mom is a little suspicious,
but she knows you and she can hear the fear in your voice. What does she do
when 'you' ask her to transfer money to the phone you're calling with?

These sorts of scams are coming. Real-time conversations with a cloned voice
scare me. So I wanted to build something to defend against them.

## What

An automated phone 'firewall' mixed with dynamic shared secrets between you and
the true caller.

A picture says a thousand words, here's a demo:


## Shared secrets

The root of my solution focuses on shared secrets between you and those you
know. Yes, you could sit down with your Gran and figure out a codeword that you
will both undoubtedly forget.

Better is to have access to your comms using self-created bots that scrape your
communications so that you have access to recent information between the two of
you.

For example, you and I have a private Slack DM where we exchange articles and
rant to each other about our boss. If I ask you a question about an article you
shared with me 2 days ago, that's an easy way to verify you are who you say you
are - no fake you has access to continuosly fresh data. A scammer is not able
to answer questions about our recent interactions.

When you setup an online account, you sometimes have to answer questions like
"What is your mother's maiden name?" etc. This is for self-verification. My
approach is for two-person verification, but relies on a similar principle of
knowing certain truths ahead-of-time.

## Technical breakdown

There are two versions: one running 'properly', that you can actually call:

+15187223932
or
+447450307731

Go on then.

The other runs locally, using your computer mic. You have to download the repo
and install dependencies etc.; maybe you want to do that?

### Part 1 - Firewall

1. Silence unknown callers from your phone settings
2. Set up conditional call forwarding to redirect silenced calls to custom number
3. Number is a Twilio number connected to a FastAPI backend
4. Backend connects to OpenAI Realtime API
5. Result: unknown callers are engaged in a conversation with a model
6. Model has sytem prompt to 'detect and rate spam'
7. Conversation is communicated in real time to app:

### Part 2 - App

1. Mobile app running on your phone
2. Receives (optional) push notifications at various stages of call
3. Receives real-time transcript of call
4. Notifies you if suspicious caller
5. Shows you ongoing verification challenge:

### Part 3 - Verification and Secrets

1. When a 'scammer' is detected, the realtime model pauses
2. A shared secret is pulled from DB (depending on who the caller says they are)
3. Caller is asked shared secret question: e.g. 'Who is the author of the book you just started reading?'
4. Answer correct: caller is verified, call is forwarded to your true number
5. Answer incorrect: hang up

#### Stack / Tools

Twilio: managing phones, handling phone-to-phone connection, patching calls as needed

OpenAI Realtime API: the 'voicemail firewall', facilitates conversation

FastAPI: backend server

Supabase: realtime communication between backend server and mobile app

Supabase: store shared secrets

Expo / React Native: mobile app

## Running

Backend is deployed and listening.

You can call +15187223932 or +447450307731 _right now_ and talk to the AI
(provided I still have credits ofc). To my fellow South Africans: I couldn't
get a Twilio number RICAed in time; forgive me.

Alternatively, clone the code and run `main.py` for an interactive version that
runs locally, using your computer mic (as opposed to your phone).

You can install the mobile app using Expo. It shows real-time progress as a
call progresses.

## Future improvements

This MVP has hard-coded secrets for particular names. You can pretend you are
David - can you guess what colour jelly beans he likes?

Dynamic secrets are the way to go. Scrape slack, email, whatsapp, etc. There
are a ton of integrations you can build. The more you know, the more you can
trust your secrets.

See todos.md

## What's in a name?

Argus - 1000-eyed giant, always vigilant and watching
Argh - the feeling you have when you get spam

Now put them together
