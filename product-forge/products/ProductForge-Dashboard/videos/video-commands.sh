#!/bin/bash

# Video generation commands
# Run these commands to create the demo video

# Create video from screenshots
ffmpeg -framerate 1 -i products\ProductForge-Dashboard\videos/screenshots/%03d.png -c:v libx264 -pix_fmt yuv420p products\ProductForge-Dashboard\videos/demo.mp4

# Add text overlays
ffmpeg -i products\ProductForge-Dashboard\videos/demo.mp4 -vf "drawtext=text='Feature Name':fontsize=24:fontcolor=red:x=10:y=10" products\ProductForge-Dashboard\videos/demo-with-overlays.mp4

# Add narration audio
ffmpeg -i products\ProductForge-Dashboard\videos/demo-with-overlays.mp4 -i products\ProductForge-Dashboard\videos/narration.wav -c:v copy -c:a aac products\ProductForge-Dashboard\videos/demo-final.mp4

