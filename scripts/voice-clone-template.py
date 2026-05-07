"""
CosyVoice TTS via Aliyun DashScope — TEMPLATE.
Copy this file to your project, replace input_text, run.

Prerequisites:
  source .venv/bin/activate
  export DASHSCOPE_API_KEY="sk-..."

Output: output.mp3 (sample rate 22050)
"""
import os
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

dashscope.api_key = os.environ['DASHSCOPE_API_KEY']
dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# Use the model + voice from voice_clone.py. Both must be the SAME pair that
# was registered when the voice was cloned.
MODEL = "cosyvoice-v3.5-plus"
VOICE = "cosyvoice-v3.5-plus-myvoice-1b98aef0e50242ad9d23ae69bb3511f7"

# === REPLACE THIS ===
input_text = """
在这里粘贴中文旁白脚本。

每段之间空一行作为自然停顿。
数字写中文（二零二六、一百五十）。
英文专有名词保留原样（Anthropic、Claude Code）。

最后一段可以是 CTA：点赞、关注、收藏，下期见。
"""
# ====================

# speech_rate tuning:
#   1.0 = natural pace
#   1.5 = ~3.7 chars/sec (good for 60-90s tight videos)
#   1.7 = faster, more energetic
synthesizer = SpeechSynthesizer(model=MODEL, voice=VOICE, speech_rate=1.5)
audio = synthesizer.call(input_text)

print(f'[Metric] requestId={synthesizer.get_last_request_id()}, '
      f'first_packet_delay={synthesizer.get_first_package_delay()}ms')

with open('output.mp3', 'wb') as f:
    f.write(audio)
print('✓ wrote output.mp3')
