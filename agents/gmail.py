"""GmailSender - SMTP SSL でMarkdownレポートをHTMLメールとして送信"""

import logging
import os
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue',
                 'Hiragino Sans', sans-serif;
    background: #f5f5f5;
    margin: 0;
    padding: 20px;
    color: #333;
  }}
  .container {{
    max-width: 800px;
    margin: 0 auto;
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }}
  .header {{
    background: #c0392b;
    color: #fff;
    padding: 24px 32px;
  }}
  .header h1 {{
    margin: 0;
    font-size: 22px;
    font-weight: 700;
  }}
  .header p {{
    margin: 6px 0 0;
    font-size: 13px;
    opacity: 0.85;
  }}
  .content {{
    padding: 24px 32px;
  }}
  h2 {{
    color: #c0392b;
    border-bottom: 2px solid #c0392b;
    padding-bottom: 6px;
    font-size: 18px;
    margin-top: 32px;
  }}
  h3 {{
    font-size: 15px;
    color: #222;
    margin: 16px 0 6px;
  }}
  blockquote {{
    border-left: 3px solid #c0392b;
    margin: 8px 0;
    padding: 4px 12px;
    color: #666;
    font-size: 13px;
  }}
  a {{
    color: #c0392b;
    text-decoration: none;
  }}
  a:hover {{
    text-decoration: underline;
  }}
  hr {{
    border: none;
    border-top: 1px solid #eee;
    margin: 24px 0;
  }}
  ul {{
    padding-left: 20px;
  }}
  li {{
    margin-bottom: 8px;
    line-height: 1.6;
  }}
  p {{
    line-height: 1.7;
    margin: 8px 0;
  }}
  .footer {{
    background: #f0f0f0;
    padding: 12px 32px;
    font-size: 12px;
    color: #888;
    text-align: center;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🇯🇵 日本株マーケットリサーチ</h1>
    <p>{date_str} {time_str} JST 生成</p>
  </div>
  <div class="content">
    {body}
  </div>
  <div class="footer">
    Japan Equity Research Agent by Claude
  </div>
</div>
</body>
</html>
"""


class GmailSender:
    def __init__(self):
        self.sender = os.environ["GMAIL_SENDER"]
        self.recipient = os.environ["GMAIL_RECIPIENT"]
        self.app_password = os.environ["GMAIL_APP_PASSWORD"]
        self.smtp_host = "smtp.gmail.com"
        self.smtp_port = 465

    def send(self, subject: str, markdown_content: str) -> None:
        """MarkdownをHTMLに変換してメール送信"""
        now = datetime.now(JST)
        date_str = now.strftime("%Y年%m月%d日")
        time_str = now.strftime("%H:%M")

        # Markdown → HTML
        body_html = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code", "nl2br"],
        )
        html_content = HTML_TEMPLATE.format(
            date_str=date_str,
            time_str=time_str,
            body=body_html,
        )

        # メッセージ構築
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient
        msg.attach(MIMEText(markdown_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        logger.info(f"[Gmail] 送信中: {self.recipient}")
        with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
            server.login(self.sender, self.app_password)
            server.sendmail(self.sender, self.recipient, msg.as_string())

        logger.info("[Gmail] 送信完了")
