# Standard library imports
import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Third-party imports
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton

# Local project-specific imports
from FinalProject.styles.styles import STYLES
from FinalProject.assets.utils import show_message
from FinalProject.assets.regex import email_regex
from FinalProject.assets.custom_errors import DatabaseError, EmailConfigError, EmailSendingError, UserNotFoundError


# Path to the user database and email configuration file
DB_FILE = os.path.join(os.getcwd(),"assets", "users_db.json")
EMAIL_CONFIG_FILE = os.path.join(os.getcwd(), "assets", "email_config.json")


def load_config() -> dict:
    """
    Loads email configuration settings from a JSON file.

    Returns:
        dict: A dictionary containing the email configuration settings.
    """
    if os.path.exists(EMAIL_CONFIG_FILE):
        try:
            with open(EMAIL_CONFIG_FILE, "r") as email_config_file:
                config = json.load(email_config_file)

                # Check if 'sender_email' and 'sender_password' are in the config
                sender_email = config.get("sender_email")
                sender_password = config.get("sender_password")

                if not sender_email or not sender_password:
                    raise EmailConfigError("Missing email or password in the configuration file.")

                print(f"ℹ️ [INFO] Email config file loaded successfully.")
                return config  # Return the config if both fields are present

        except json.JSONDecodeError as e:
            print(f"❌ [ERROR] Error decoding email config file: {e}")
            show_message(None, "Configuration Error", f"Failed to decode email config: {e}")
            raise EmailConfigError(f"Failed to decode email config: {e}")

    else:
        print(f"❌ [ERROR] Email config file not found at {EMAIL_CONFIG_FILE}")
        show_message(None, "Configuration Error", f"Config file not found at {EMAIL_CONFIG_FILE}")
        raise EmailConfigError(f"Config file not found at {EMAIL_CONFIG_FILE}")

    return {}

class EmailSender:
    """
    Class responsible for sending password recovery emails.
    It handles creating and sending an email with a recovery link or password.
    """
    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str) -> None:
        """
        Initialize the email sender with necessary SMTP details.

        Args:
            smtp_server (str): The SMTP server address.
            smtp_port (int): The SMTP server port.
            sender_email (str): The email address used to send the emails.
            sender_password (str): The password for the sender's email.
        """
        print(f"🔄 [INFO] Initializing EmailSender with SMTP server {smtp_server} and port {smtp_port}.")
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password

    def send_recovery_email(self, recipient_email: str, username: str) -> None:
        """
        Sends a password recovery email to the specified recipient.

        Args:
            recipient_email (str): The email address of the user requesting password recovery.
            username (str): The username of the user requesting recovery.
        """
        # Email subject and body content
        subject = "Password Recovery"
        body = f"Hello {username},\n\nWe received a request to recover your password.\n" \
               f"Your password is: ['password_hash']\n\n" \
               "If you did not request this, please ignore this message."

        # Create the email message with the sender, recipient, subject, and body
        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        print(f"⏳ [INFO] Preparing to send recovery email to {recipient_email} for the user '{username}'.")

        try:
            # Connect to the SMTP server and send the email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Secure connection using TLS
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_email, msg.as_string())
            print(f"✅ [SUCCESS] Recovery email successfully sent to {recipient_email}.")

        except smtplib.SMTPAuthenticationError:
            print("❌ [ERROR] Authentication error, check the email server credentials.")
            raise EmailSendingError("Authentication error: Unable to authenticate with SMTP server.")

        except smtplib.SMTPConnectError:
            print("❌ [ERROR] Unable to connect to SMTP server.")
            raise EmailSendingError("Connection error: Could not connect to SMTP server.")

        except Exception as e:
            print(f"❌ [ERROR] Failed to send email: {e}")
            raise EmailSendingError(f"Failed to send the recovery email: {e}")

class RecoveryWindow(QWidget):
    """
    Window for password recovery via email.

    This class defines the user interface and functionality for recovering a user's password
    through an email-based recovery process. It allows users to input their email, check if
    the email exists, and send them their password if the email is valid.
    """
    def __init__(self) -> None:
        super().__init__()

        # Set the window's title and initial geometry
        self.setWindowTitle("Password Recovery")
        self.setGeometry(100, 100, 400, 300)

        # Create the layout and widgets for the recovery window
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center-align all widgets
        layout.setSpacing(20)  # Add spacing between widgets

        # Create and configure the email input field
        self.email_input = QLineEdit()
        self.email_input.setStyleSheet(STYLES["text_field"])  # Apply custom styling
        self.email_input.setPlaceholderText("Enter your email")

        # Create and configure the "Send Recovery Email" button
        self.recover_button = QPushButton("Send Recovery Email")
        self.recover_button.setStyleSheet(STYLES["button"])
        self.recover_button.clicked.connect(self.recover_password) # Connect button click to method

        # Add input field and button to the layout
        layout.addWidget(self.email_input)
        layout.addWidget(self.recover_button)

        # Set the layout for the window
        self.setLayout(layout)

        try:
            # Load email configuration from the config file
            config = load_config()
            sender_email = config.get("sender_email")
            sender_password = config.get("sender_password")

            if not sender_email or not sender_password:
                print(f"❌ [ERROR] Missing email or password in the configuration file.")
                show_message(self, "Configuration Error", "Missing email or password in configuration file.")
                raise EmailConfigError("Missing email or password in configuration file.")

            print("ℹ️ [INFO] Email configuration loaded successfully.")

            # Initialize the EmailSender with necessary SMTP details
            self.email_sender = EmailSender(smtp_server="smtp.gmail.com",
                                            smtp_port=587,
                                            sender_email=sender_email,
                                            sender_password=sender_password
                                            )

        except EmailConfigError as e:
            show_message(self, "Configuration Error", str(e))
            print(f"❌ [ERROR] {e}")
            raise e

    def recover_password(self) -> None:
        """
        Trigger password recovery via email.

        This method checks whether the provided email is valid and corresponds to an existing user.
        If so, it sends a password recovery email to that email address. If the email is not found,
        it informs the user and clears the input field.
        """
        email = self.email_input.text() # Get the email entered by the user

        # Check if the email is valid
        user = self.find_user_by_email(email)
        if user:
            print(f"🔄 [INFO] Sending recovery email to {email}...")
            try:
                # Send the recovery email
                self.email_sender.send_recovery_email(email, user)
                show_message(self, "Success", "A recovery email has been sent.")
                self.close() # Close the recovery window after sending the email
                print("📝 [INFO] Recovery window closed.")
            except Exception as e:
                show_message(self, "Error", str(e))
                print(f"❌ [ERROR] Failed to send recovery email: {e}")
        else:
            # If email not found, notify the user and clear the email input
            print(f"❌ [ERROR] No user found with email {email}.")
            show_message(self, "Error", "Email not found. Please try again.")
            self.email_input.clear()

    @staticmethod
    def find_user_by_email(email: str) -> str | None:
        """
        Find a user by their email.

        Searches through the users database to find a match for the provided email.
        If a match is found, returns the username; otherwise, returns None.

        Args:
            email (str): The email to search for.

        Returns:
            str or None: The username if found, else None.
        """
        email = email.strip().lower()
        users_db = RecoveryWindow.load_users_db() # Load the user database
        for username, details in users_db.items():
            if details.get("email").strip().lower() == email:
                print(f"🔍 [INFO] User '{username}' found with email {email}.")
                return username # Return the username associated with the email
        print(f"❌ [ERROR] No user found with email {email}.")
        raise UserNotFoundError(email)

    @staticmethod
    def validate_users_db(db: dict) -> bool:
        """
        Validates the structure of the user's database.

        Args:
            db (dict): The user's database.

        Returns:
            bool: True if the database is valid, False otherwise.
        """
        print("⏳ [INFO] Validating the structure of the users database...")
        for username, details in db.items():
            # Ensure 'email' and 'password_hash' are present for each user
            if "email" not in details or "password_hash" not in details:
                raise DatabaseError(f"Missing fields for user '{username}': {details}")
            # Validate the email format using regex
            if not re.fullmatch(email_regex, details["email"]):
                raise DatabaseError(f"Invalid email format for user '{username}': {details['email']}")
        print("✅ [SUCCESS] The users database structure is valid.")
        return True # Return True if all users are valid

    @staticmethod
    def load_users_db() -> dict:
        """
        Loads the user database from a JSON file.

        Reads the data from 'users_db.json' and validates the database structure.

        Returns:
            dict: A dictionary containing the users, or an empty dictionary if loading fails.
        """
        print("⏳ [INFO] Loading users database...")
        try:
            # Check if the database file exists
            if not os.path.exists(DB_FILE):
                print(f"❌ [ERROR] Database file not found at {DB_FILE}")
                raise DatabaseError(f"Database file not found at {DB_FILE}")

            with open(DB_FILE, "r") as file:
                data = json.load(file)

                # Validate the structure of the database
                if not RecoveryWindow.validate_users_db(data):
                    print("❌ [ERROR] Invalid user database structure.")
                    raise DatabaseError("Invalid user database structure.")
                return data

            print("✅ [SUCCESS] Users database loaded successfully.")
            return data

        except FileNotFoundError:
            print(f"❌ [ERROR] Database file not found at {DB_FILE}")
            show_message(None, "File Error", f"Database file not found at {DB_FILE}")
        except json.JSONDecodeError as e:
            print(f"❌ [ERROR] Error decoding database JSON: {e}")
            show_message(None, "JSON Error", f"Failed to decode database JSON: {e}")
        except Exception as e:
            print(f"❌ [ERROR] Unexpected error loading the database: {e}")
            show_message(None, "Error", f"Unexpected error: {e}")

        return {}  # Return an empty dictionary if any error occurs


