from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select
from datetime import datetime, timedelta
from fpdf import FPDF
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from core.database import engine
from models import Feedback
from core.config import settings
from core.logger import get_logger
import os
import base64
import io

logger = get_logger(__name__)
scheduler = AsyncIOScheduler()

# Email Configuration
# Email Configuration
conf = None
if settings.MAIL_USERNAME and settings.MAIL_PASSWORD and settings.MAIL_FROM and settings.MAIL_PORT and settings.MAIL_SERVER:
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME or "Feedback System",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True
    )
else:
    logger.warning("Email configuration missing. Email reports will be disabled.")

class PDF(FPDF):
    def header(self):
        # Premium Header
        self.set_fill_color(33, 37, 41) # Dark Background
        self.rect(0, 0, 210, 30, 'F')
        
        self.set_y(10)
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(255, 255, 255) # White Text
        self.cell(0, 10, 'Daily Feedback Report', 0, 1, 'C')
        
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(200, 200, 200) # Light Gray
        self.cell(0, 5, f"Generated on: {datetime.now().strftime('%B %d, %Y at %H:%M')}", 0, 1, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def table_header(self):
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(233, 236, 239) # Header Gray
        self.set_text_color(33, 37, 41)
        self.set_draw_color(222, 226, 230)
        self.set_line_width(0.3)
        
        # Column Widths
        self.w_time = 25
        self.w_ro = 25
        self.w_method = 20 # New Column
        self.w_phone = 30
        self.w_rating = 20
        self.w_comment = 30 # Reduced to fit Method
        self.w_photos = 40
        
        self.cell(self.w_time, 8, 'Time', 1, 0, 'C', 1)
        self.cell(self.w_ro, 8, 'RO #', 1, 0, 'C', 1)
        self.cell(self.w_method, 8, 'Method', 1, 0, 'C', 1) # New Header
        self.cell(self.w_phone, 8, 'Phone', 1, 0, 'C', 1)
        self.cell(self.w_rating, 8, 'Ratings', 1, 0, 'C', 1)
        self.cell(self.w_comment, 8, 'Comment', 1, 0, 'C', 1)
        self.cell(self.w_photos, 8, 'Photos', 1, 1, 'C', 1)

    def table_row(self, feedback, fill):
        self.set_font('Helvetica', '', 8)
        self.set_text_color(50, 50, 50)
        self.set_fill_color(248, 249, 250) if fill else self.set_fill_color(255, 255, 255)
        
        # Calculate height based on comment length
        # Standard height is 15, but comment might expand it
        # MultiCell simulation to get height
        x_start = self.get_x()
        y_start = self.get_y()
        
        # Ratings String
        air_rating = f"Air: {feedback.rating_air}/3" if feedback.rating_air else "Air: -"
        wash_rating = f"W/R: {feedback.rating_washroom}/3" if feedback.rating_washroom else "W/R: -"
        ratings_text = f"{air_rating}\n{wash_rating}"
        
        # Determine Row Height (Max of content)
        # We'll fix it to 20mm for compactness and consistency with thumbnails
        row_height = 20
        
        # Check for page break
        if y_start + row_height > 270:
            self.add_page()
            self.table_header()
            y_start = self.get_y()
            x_start = self.get_x()

        # Draw Cells
        # Time
        self.cell(self.w_time, row_height, feedback.created_at.strftime('%H:%M'), 1, 0, 'C', fill)
        
        # RO Number
        ro_text = feedback.ro_number if feedback.ro_number else "-"
        self.cell(self.w_ro, row_height, ro_text, 1, 0, 'C', fill)

        # Method
        method_text = feedback.feedback_method if feedback.feedback_method else "-"
        self.cell(self.w_method, row_height, method_text, 1, 0, 'C', fill)
        
        # Phone
        self.cell(self.w_phone, row_height, feedback.phone, 1, 0, 'C', fill)
        
        # Ratings (MultiLine)
        x_rating = self.get_x()
        self.cell(self.w_rating, row_height, "", 1, 0, 'C', fill) # Border only
        self.set_xy(x_rating, y_start)
        self.multi_cell(self.w_rating, row_height/2, ratings_text, 0, 'C')
        self.set_xy(x_rating + self.w_rating, y_start)
        
        # Comment (MultiLine)
        x_comment = self.get_x()
        self.cell(self.w_comment, row_height, "", 1, 0, 'L', fill) # Border only
        self.set_xy(x_comment, y_start)
        # Truncate comment if too long for fixed height? Or just let it clip?
        # Let's use multi_cell with a small font
        comment_text = feedback.comment or "-"
        self.set_font('Helvetica', '', 7)
        self.multi_cell(self.w_comment, 4, comment_text, 0, 'L')
        self.set_font('Helvetica', '', 8)
        self.set_xy(x_comment + self.w_comment, y_start)
        
        # Photos
        x_photos = self.get_x()
        self.cell(self.w_photos, row_height, "", 1, 1, 'C', fill) # Border and new line
        
        # Add Thumbnails
        # We have 3 slots in 40mm width -> ~12mm each
        # Height 20mm -> max img height ~18mm
        
        def add_thumb(img_bytes, offset_x):
            if img_bytes:
                try:
                    img_stream = io.BytesIO(img_bytes)
                    # Fit in 12x18 box
                    self.image(img_stream, x=x_photos + offset_x, y=y_start + 1, w=12, h=18)
                except Exception:
                    pass

        add_thumb(feedback.photo_air, 1)
        add_thumb(feedback.photo_washroom, 14)
        add_thumb(feedback.photo_receipt, 27)

def generate_pdf(feedbacks, filename):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Summary Section
    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(33, 37, 41)
    
    total = len(feedbacks)
    # Calculate averages ignoring None
    air_ratings = [f.rating_air for f in feedbacks if f.rating_air]
    wash_ratings = [f.rating_washroom for f in feedbacks if f.rating_washroom]
    
    avg_air = sum(air_ratings)/len(air_ratings) if air_ratings else 0
    avg_wash = sum(wash_ratings)/len(wash_ratings) if wash_ratings else 0
    
    pdf.cell(0, 8, f"Summary Overview", 0, 1)
    pdf.set_font("Helvetica", '', 10)
    pdf.cell(50, 6, f"Total Feedback: {total}", 0, 0)
    pdf.cell(50, 6, f"Avg Air Rating: {avg_air:.1f}/3", 0, 0)
    pdf.cell(50, 6, f"Avg Washroom Rating: {avg_wash:.1f}/3", 0, 1)
    pdf.ln(5)
    
    # Table Header
    pdf.table_header()
    
    # Rows
    fill = False
    for feedback in feedbacks:
        pdf.table_row(feedback, fill)
        fill = not fill # Toggle zebra striping
        
    pdf.output(filename)

async def send_email_report(filename):
    if not conf:
        logger.warning("Email configuration missing. Skipping email report.")
        return

    # Support multiple recipients (comma-separated)
    recipients = [email.strip() for email in settings.MAIL_TO.split(',')] if settings.MAIL_TO else []
    
    message = MessageSchema(
        subject="Daily Feedback Report",
        recipients=recipients, 
        body="Attached is the daily feedback report.",
        subtype=MessageType.html,
        attachments=[filename]
    )
    # Update conf to use MAIL_FROM_NAME if supported by fastapi-mail or just rely on MAIL_FROM
    # fastapi-mail ConnectionConfig doesn't directly take MAIL_FROM_NAME in older versions, 
    # but we can try to format MAIL_FROM if needed. 
    # For now, let's just ensure it's consistent.
    fm = FastMail(conf)
    await fm.send_message(message)

async def generate_daily_report():
    logger.info(f"Generating daily report for {datetime.now()}")
    try:
        with Session(engine) as session:
            # Fetch feedback for the last interval (e.g., last 24 hours)
            time_threshold = datetime.utcnow() - timedelta(minutes=settings.REPORT_INTERVAL_MINUTES)
            statement = select(Feedback).where(Feedback.created_at >= time_threshold)
            feedbacks = session.exec(statement).all()
            
            if feedbacks:
                filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                generate_pdf(feedbacks, filename)
                try:
                    await send_email_report(filename)
                    logger.info(f"Report sent to {settings.MAIL_TO}")
                except Exception as e:
                    logger.error(f"Failed to send email: {e}")
                finally:
                    if os.path.exists(filename):
                        os.remove(filename)
            else:
                logger.info("No feedback to report.")
    except Exception as e:
        import traceback
        logger.error(f"Error generating daily report: {e}")
        logger.error(traceback.format_exc())

def generate_feedback_html(feedback: Feedback) -> str:
    """Generates HTML body for feedback email with embedded images."""
    
    def get_image_html(img_bytes, label):
        if not img_bytes:
            return ""
        try:
            b64_img = base64.b64encode(img_bytes).decode('utf-8')
            return f'''
            <div style="margin-bottom: 15px;">
                <p><strong>{label}:</strong></p>
                <img src="data:image/jpeg;base64,{b64_img}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;">
            </div>
            '''
        except Exception:
            return ""

    air_img = get_image_html(feedback.photo_air, "Air Facility Photo")
    wash_img = get_image_html(feedback.photo_washroom, "Washroom Photo")
    receipt_img = get_image_html(feedback.photo_receipt, "Receipt Photo")

    return f'''
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #d9534f;">Negative Feedback Alert</h2>
            <p><strong>Phone:</strong> {feedback.phone}</p>
            <p><strong>Time:</strong> {feedback.created_at.strftime('%Y-%m-%d %H:%M')}</p>
            <p><strong>RO Number:</strong> {feedback.ro_number or '-'}</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #d9534f; margin: 20px 0;">
                <p><strong>Air Rating:</strong> {feedback.rating_air}/3</p>
                <p><strong>Washroom Rating:</strong> {feedback.rating_washroom}/3</p>
                <p><strong>Comment:</strong> {feedback.comment or 'No comment'}</p>
            </div>

            <h3>Attached Photos:</h3>
            {air_img}
            {wash_img}
            {receipt_img}
            
            <p style="font-size: 12px; color: #777; margin-top: 30px;">
                This is an automated message. Please check the attached PDF for full details.
            </p>
        </body>
    </html>
    '''

async def send_immediate_negative_report(feedback_id: int):
    logger.info(f"Generating immediate negative report for feedback {feedback_id}")
    try:
        with Session(engine) as session:
            feedback = session.get(Feedback, feedback_id)
            if not feedback:
                logger.error(f"Feedback {feedback_id} not found")
                return

            filename = f"urgent_report_{feedback_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            generate_pdf([feedback], filename)
            
            try:
                html_body = generate_feedback_html(feedback)
                if not conf:
                    logger.warning("Email configuration missing. Skipping immediate negative report.")
                    return

                # Support multiple recipients (comma-separated)
                recipients = [email.strip() for email in settings.MAIL_TO.split(',')] if settings.MAIL_TO else []
                
                message = MessageSchema(
                    subject="URGENT: Negative Feedback Received",
                    recipients=recipients, 
                    body=html_body,
                    subtype=MessageType.html,
                    attachments=[filename]
                )
                fm = FastMail(conf)
                await fm.send_message(message)
                logger.info(f"Immediate report sent to {settings.MAIL_TO}")
            except Exception as e:
                logger.error(f"Failed to send immediate email: {e}")
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
    except Exception as e:
        logger.error(f"Error generating immediate report: {e}")

def start_scheduler():
    try:
        # Use interval trigger based on settings
        scheduler.add_job(
            generate_daily_report, 
            'interval', 
            minutes=settings.REPORT_INTERVAL_MINUTES
        )
        scheduler.start()
        logger.info(f"Scheduler started. Report scheduled every {settings.REPORT_INTERVAL_MINUTES} minutes.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
