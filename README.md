# EmoConnect

## Overview

**EmoConnect** is an emotion-aware companion robot system designed to provide empathetic and emotionally supportive interactions, with a particular focus on addressing loneliness among elderly users in Singapore. The system integrates real-time emotion perception with natural, context-aware dialogue to create more human-like and emotionally sensitive conversations.

At its core, EmoConnect leverages the **Furhat virtual robot** to interact with users audibly while simultaneously analysing facial expressions captured through a webcam. By combining visual emotion recognition with large language model (LLM)–driven dialogue, the robot adapts its responses to the user’s inferred emotional state, enabling more meaningful and supportive interactions.

## System Architecture

EmoConnect is composed of two primary sub-systems that run concurrently under a Python-based controller:

### 1. User Perception Sub-system

* Captures live video input from a webcam.
* Performs real-time facial expression analysis using a deep learning model based on a CNN architecture.
* Classifies user emotions and continuously updates the inferred emotional state.

### 2. Interaction Sub-system

* Utilises the Furhat virtual robot for speech output and interaction management.
* Integrates **Gemini LLM** to generate context-aware and emotionally adaptive responses.
* Adjusts conversational tone, content, and flow based on detected emotional cues.

## Key Features

* Real-time facial emotion recognition
* Emotion-aware conversational responses
* Auditory interaction via Furhat virtual robot
* Modular architecture for perception and interaction
* LLM-powered dialogue

## Getting Started

Follow the steps below to run the EmoConnect bot locally.

### Prerequisites

* Python installed on your system
* Webcam access
* Furhat Virtual Robot (Simulator) installed and running

### Setup & Usage

1. **Activate the virtual environment**
   Use the existing virtual environment from **Assignment 0**.

2. **Add environment variables**
   Create a `.env` file in the project root directory and add your Gemini API key:

   ```
   GEMINI_API_KEY=your_api_key_here
   ```

3. **Run the controller**
   In your terminal, start the system by running:

   ```
   python controller.py
   ```

4. **Start the interaction**
   Press the **Start** button in the interface to begin the EmoConnect interaction.

5. **End the session**
   Press the **Stop** button to safely terminate the system.

## Project Goal

The goal of EmoConnect is to explore how emotion recognition and large language models can be combined to enhance human–robot interaction, particularly in assistive and companionship scenarios for elderly users. By responding not only to *what* users say but also to *how* they feel, EmoConnect aims to foster more emotionally intelligent and supportive interactions.

## Future Work

* Improving emotion classification accuracy
* Expanding multimodal perception (e.g., voice emotion analysis)
* Long-term user adaptation and personalization
* Deployment on physical robot platforms

---

*EmoConnect — Bridging emotional intelligence and human–robot interaction.*
