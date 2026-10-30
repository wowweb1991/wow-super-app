
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
    <meta name="viewport"
          content="width=device-width, initial-scale=1">
    <title>WOW Super App</title>
    </head>
    <body style="background:#081426;color:white;
                 font-family:Arial;text-align:center;
                 padding:40px">
    <h1>WOW SUPER APP</h1>
    <p>Connect • Buy • Sell • Create • Grow</p>
    <h2>🛍️ Marketplace</h2>
    <h2>👥 Community</h2>
    <h2>💼 Services</h2>
    <h2>✨ AI Studio</h2>
    </body>
    </html>
    """
