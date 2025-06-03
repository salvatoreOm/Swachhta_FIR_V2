# Swachhta FIR - Railway Station Cleanliness Complaint System

A bilingual (English/Hindi) web application for reporting and managing cleanliness complaints at railway stations.

## Features

- QR code-based complaint submission
- Multiple photo upload support
- Mobile number verification via OTP
- Bilingual interface (English/Hindi)
- Admin dashboard for complaint management
- Real-time status updates

## Prerequisites

- Python 3.x
- Django 5.2.1
- Fast2SMS account for OTP delivery

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/swachhta-fir.git
cd swachhta-fir
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create .env file in project root:
```
FAST2SMS_API_KEY=your_fast2sms_api_key_here
DJANGO_SECRET_KEY=your_secure_secret_key_here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create superuser:
```bash
python manage.py createsuperuser
```

7. Compile translations:
```bash
python manage.py compilemessages
```

8. Run development server:
```bash
python manage.py runserver
```

## Usage

1. Access admin panel at `/admin` to add stations
2. Generate QR codes for each platform
3. Place QR codes at stations
4. Users can scan QR codes to submit complaints
5. Staff can manage complaints through dashboard

## Translation

To update translations:

1. Extract messages:
```bash
python manage.py makemessages -l hi
```

2. Edit translations in `locale/hi/LC_MESSAGES/django.po`

3. Compile messages:
```bash
python manage.py compilemessages
```

## Production Deployment

1. Set DEBUG=False in .env
2. Add your domain to ALLOWED_HOSTS
3. Configure proper database (PostgreSQL recommended)
4. Set up static/media file serving
5. Configure web server (Nginx/Apache)
6. Set up SSL certificate

## Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
