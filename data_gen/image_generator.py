from google import genai
from google.genai import types
from google.genai.errors import ServerError
from PIL import Image
import os
import time

class ImageGenerator:
    #gemini-3-pro-image-preview as expensive model
    # gemini-2.5-flash-image as cheaper model
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-image") -> Image:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_image(self, prompt: str, output_path: str, aspect_ratio: str, resolution: str) -> None:
        """
        aspect_ratio = "16:9" # "1:1","2:3","3:2","3:4","4:3","4:5","5:4","9:16","16:9","21:9"

        resolution = "2K" # "1K", "2K", "4K"
        """
        max_retries = 10
        for i in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                        ),
                    )
                )
                for part in response.parts:
                    if image := part.as_image():
                        if directory := os.path.dirname(output_path):
                            os.makedirs(directory, exist_ok=True)
                        image.save(output_path)
                        #print(f"Image saved to {output_path}")
                        return image
                raise ValueError("No image generated from the prompt.")
            except ServerError as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    wait_time = (i + 1) * 5
                    print(f"ImageGenerator: Server overloaded (503). Retrying in {wait_time}s... (Attempt {i+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise e
        
        raise ServerError(f"Failed to generate image after {max_retries} retries due to server overload.")
