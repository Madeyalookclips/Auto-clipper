import os, re, json
from flask import Flask, request, render_template_string
from youtube_transcript_api import YouTubeTranscriptApi
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PAGE = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auto Clipper</title>
<style>
body{font-family:sans-serif;background:#111;color:#eee;max-width:640px;margin:auto;padding:16px}
input,textarea{width:100%;padding:12px;font-size:16px;border-radius:8px;border:0;margin-bottom:10px;box-sizing:border-box}
textarea{height:140px}
button{width:100%;padding:12px;font-size:16px;border-radius:8px;border:0;background:#ff0050;color:#fff}
.clip{background:#1e1e1e;border-radius:10px;padding:14px;margin-top:14px}
.time{color:#25f4ee;font-weight:bold}
.tags{color:#aaa}
.hint{color:#aaa;font-size:14px}
</style>
</head>
<body>
<h2>Auto Clipper</h2>
<form method="post">
<input name="url" placeholder="YouTube link (optional if you paste a transcript)" value="{{ url or '' }}">
<textarea name="transcript" placeholder="Or paste the transcript here"></textarea>
<p class="hint">If the link doesn't work, paste the transcript with timestamps instead.</p>
<button type="submit">Find best clips</button>
</form>
{% if error %}<p style="color:#ff6b6b">{{ error }}</p>{% endif %}
{% for c in clips %}
<div class="clip">
<div class="time">{{ c.start }} to {{ c.end }}</div>
<h3>{{ c.hook }}</h3>
<p>{{ c.caption }}</p>
<p class="tags">{{ c.hashtags }}</p>
<p><i>{{ c.why }}</i></p>
</div>
{% endfor %}
</body>
</html>
"""


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def fmt(sec):
    sec = int(sec)
    return f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}"


@app.route("/", methods=["GET", "POST"])
def home():
    clips, error, url = [], None, None
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        transcript = request.form.get("transcript", "").strip()

        if not transcript:
            vid = video_id(url)
            if not vid:
                error = "Paste a YouTube link or a transcript."
            else:
                try:
                    entries = YouTubeTranscriptApi.get_transcript(vid)
                    lines = [f"[{fmt(e['start'])}] {e['text']}" for e in entries]
                    transcript = "\n".join(lines)
                except Exception:
                    error = "YouTube blocked the transcript. Paste it into the box instead."

        if transcript:
            transcript = transcript[:150000]
            prompt = (
                "You find viral short-form clips from stream transcripts. "
                "From the transcript below, pick the 8 best moments for TikTok. "
                "Each clip should be 20 to 60 seconds, start on a strong hook, "
                "and be self-contained. Look for funny moments, big reactions, "
                "hot takes, stories, and drama. Return ONLY a JSON list. "
                "Each item has: start, end (HH:MM:SS), hook (a punchy on-screen "
                "title), caption (one or two sentences), hashtags (a string), "
                "why (one sentence).\n\n" + transcript
            )
            try:
                resp = client.messages.create(
                    model="claude-sonnet-5-5",
                    max_tokens=16000,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = "".join(b.text for b in resp.content if b.type == "text")

                text = text[text.find("["):text.rfind("]") + 1]
                clips = [type("C", (), d) for d in json.loads(text)]
            except Exception as e:
                error = f"Something went wrong: {e}"
    return render_template_string(PAGE, clips=clips, error=error, url=url)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
