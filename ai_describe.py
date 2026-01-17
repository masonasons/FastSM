"""AI-powered image description using OpenAI GPT-4 Vision or Google Gemini."""

import base64
import requests
from application import get_app


def get_image_description(image_url):
	"""Get an AI-generated description of an image.

	Args:
		image_url: URL of the image to describe

	Returns:
		tuple: (success: bool, description: str or error message)
	"""
	prefs = get_app().prefs
	service = prefs.ai_service
	prompt = prefs.ai_image_prompt

	if service == "none" or not service:
		return (False, "AI image description is disabled. Enable it in Options > AI.")

	if service == "openai":
		return _describe_with_openai(image_url, prompt, prefs.openai_api_key, prefs.openai_model)
	elif service == "gemini":
		return _describe_with_gemini(image_url, prompt, prefs.gemini_api_key, prefs.gemini_model)
	else:
		return (False, f"Unknown AI service: {service}")


def _describe_with_openai(image_url, prompt, api_key, model):
	"""Use OpenAI to describe an image."""
	if not api_key:
		return (False, "OpenAI API key not configured. Add it in Options > AI.")

	try:
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json"
		}

		payload = {
			"model": model,
			"messages": [
				{
					"role": "user",
					"content": [
						{"type": "text", "text": prompt},
						{
							"type": "image_url",
							"image_url": {"url": image_url}
						}
					]
				}
			],
			"max_tokens": 1000
		}

		response = requests.post(
			"https://api.openai.com/v1/chat/completions",
			headers=headers,
			json=payload,
			timeout=60
		)

		if response.status_code != 200:
			error_data = response.json() if response.text else {}
			error_msg = error_data.get("error", {}).get("message", response.text)
			return (False, f"OpenAI API error: {error_msg}")

		data = response.json()
		description = data["choices"][0]["message"]["content"]
		return (True, description)

	except requests.exceptions.Timeout:
		return (False, "Request timed out. Please try again.")
	except requests.exceptions.RequestException as e:
		return (False, f"Network error: {str(e)}")
	except Exception as e:
		return (False, f"Error: {str(e)}")


def _describe_with_gemini(image_url, prompt, api_key, model):
	"""Use Google Gemini to describe an image."""
	if not api_key:
		return (False, "Gemini API key not configured. Add it in Options > AI.")

	try:
		# First, download the image and convert to base64
		img_response = requests.get(image_url, timeout=30)
		img_response.raise_for_status()
		image_data = base64.b64encode(img_response.content).decode('utf-8')

		# Detect mime type from content-type header or default to jpeg
		content_type = img_response.headers.get('content-type', 'image/jpeg')
		if ';' in content_type:
			content_type = content_type.split(';')[0].strip()

		# Gemini API endpoint
		url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

		payload = {
			"contents": [
				{
					"parts": [
						{"text": prompt},
						{
							"inline_data": {
								"mime_type": content_type,
								"data": image_data
							}
						}
					]
				}
			]
		}

		response = requests.post(
			url,
			json=payload,
			timeout=60
		)

		if response.status_code != 200:
			error_data = response.json() if response.text else {}
			error_msg = error_data.get("error", {}).get("message", response.text)
			return (False, f"Gemini API error: {error_msg}")

		data = response.json()

		# Extract text from Gemini response
		candidates = data.get("candidates", [])
		if not candidates:
			return (False, "Gemini returned no response")

		content = candidates[0].get("content", {})
		parts = content.get("parts", [])
		if not parts:
			return (False, "Gemini returned empty response")

		description = parts[0].get("text", "")
		if not description:
			return (False, "Gemini returned no description")

		return (True, description)

	except requests.exceptions.Timeout:
		return (False, "Request timed out. Please try again.")
	except requests.exceptions.RequestException as e:
		return (False, f"Network error: {str(e)}")
	except Exception as e:
		return (False, f"Error: {str(e)}")
