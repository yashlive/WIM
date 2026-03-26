import smtplib
from email.message import EmailMessage

# Email credentials
sender_email = "yashsaiwal.live@gmail.com"         # Replace with your Gmail address
receiver_email = "yash.saiwal@adani.com"  # Replace with receiver's email
app_password = "dckl okxt nwxd hhqr"       # Replace with 16-digit app password

# Read the weather report
try:
    with open("weather_report.txt", "r") as file:
        body = file.read()
except FileNotFoundError:
    print("❌ weather_report.txt not found. Make sure the report file exists.")
    exit()

# Compose email
message = EmailMessage()
message["Subject"] = "🌦️ Daily Weather Forecast Report"
message["From"] = sender_email
message["To"] = receiver_email
message.set_content(body)

# Send the email
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.send_message(message)
        print("✅ Email sent successfully.")
except Exception as e:
    print(f"❌ Failed to send email: {e}")
