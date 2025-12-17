import React, { useState, useEffect, useRef } from 'react'
import './SpeechToText.css'

function SpeechToText({ onTranscript, disabled }) {
  const [isListening, setIsListening] = useState(false)
  const [isSupported, setIsSupported] = useState(false)
  const recognitionRef = useRef(null)

  useEffect(() => {
    // Check if browser supports Speech Recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    
    if (SpeechRecognition) {
      setIsSupported(true)
      const recognition = new SpeechRecognition()
      
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'en-US'

      recognition.onstart = () => {
        setIsListening(true)
      }

      recognition.onresult = (event) => {
        let interimTranscript = ''
        let finalTranscript = ''

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            finalTranscript += transcript + ' '
          } else {
            interimTranscript += transcript
          }
        }

        // Update with interim results for real-time feedback
        if (interimTranscript) {
          onTranscript(interimTranscript, false)
        }

        // Send final transcript when complete
        if (finalTranscript) {
          onTranscript(finalTranscript.trim(), true)
          setIsListening(false)
        }
      }

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
        
        // Handle specific errors
        if (event.error === 'no-speech') {
          // User didn't speak, just stop listening
          setIsListening(false)
        } else if (event.error === 'not-allowed') {
          alert('Microphone permission denied. Please enable microphone access in your browser settings.')
        } else {
          alert(`Speech recognition error: ${event.error}`)
        }
      }

      recognition.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current = recognition
    } else {
      setIsSupported(false)
    }

    // Cleanup
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
    }
  }, [onTranscript])

  const toggleListening = () => {
    if (!isSupported) {
      alert('Speech recognition is not supported in your browser. Please use Chrome, Edge, or Safari.')
      return
    }

    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
    } else {
      try {
        recognitionRef.current?.start()
      } catch (error) {
        console.error('Error starting speech recognition:', error)
        alert('Could not start speech recognition. Please check your microphone permissions.')
      }
    }
  }

  if (!isSupported) {
    return null // Don't show button if not supported
  }

  return (
    <button
      type="button"
      className={`speech-button ${isListening ? 'listening' : ''}`}
      onClick={toggleListening}
      disabled={disabled}
      title={isListening ? 'Stop recording' : 'Start voice input'}
      aria-label={isListening ? 'Stop recording' : 'Start voice input'}
    >
      {isListening ? (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>
        </svg>
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z" fill="currentColor"/>
          <path d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H3V12C3 16.97 7.03 21 12 21C16.97 21 21 16.97 21 12V10H19Z" fill="currentColor"/>
          <path d="M11 22H13V24H11V22Z" fill="currentColor"/>
        </svg>
      )}
      {isListening && <span className="pulse-ring"></span>}
    </button>
  )
}

export default SpeechToText

