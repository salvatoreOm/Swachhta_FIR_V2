# User Authentication and Permission System

## Overview
The Railway Station Cleanliness system now has a proper user authentication and permission system that separates regular station managers from administrators.

## User Types

### 1. Superuser/Staff (Administrators)
- Can access Django admin panel via `/admin/`
- Can manage all cities, stations, and complaints
- Can create and manage multiple stations
- Can assign station managers to stations

### 2. Station Managers (Regular Users)
- **Cannot access Django admin panel** - automatically redirected to user dashboard
- Can only create and manage **ONE station**
- Can only view complaints for their assigned station
- Limited permissions focused on their specific station

## Authentication Features

### Login System
- **Login URL**: `/login/`
- Users login with email and password
- Automatic redirection based on user type:
  - Admins → Admin dashboard
  - Station managers → User dashboard

### Password Reset
- Forgot password functionality via email
- Complete password reset flow with secure tokens
- Email templates styled to match the system theme

### Permission Restrictions
- Regular users cannot access admin panel (middleware protection)
- Users can only manage complaints and data for their assigned station
- Automatic permission checks in all views

## Setting Up Users

### For Administrators (via Django Admin)
1. Login to admin panel: `/admin/`
2. Create users in Users section
3. Create UserProfile to assign stations
4. Set appropriate permissions

### For Station Managers (via Management Command)
```bash
python manage.py create_station_user --username manager1 --email manager@example.com --password securepass
```

## Station Assignment Process

### For Regular Users:
1. User logs in for the first time
2. If no station assigned, they can create ONE station via "Setup Station"
3. Once station is created, they can only manage that station
4. Cannot create additional stations

### For Administrators:
- Can create multiple stations
- Can assign managers to stations
- Can manage all system data

## Access Control

### URLs Protected by Login:
- `/dashboard/` - User dashboard (station managers)
- `/admin-dashboard/` - Admin dashboard (superusers/staff only)
- `/station-setup/` - Station creation (limited to one per regular user)
- All complaint management URLs

### Automatic Redirections:
- Root URL (`/`) → Login page
- Regular users trying to access admin → User dashboard
- Unauthenticated users → Login page

## Security Features

1. **Middleware Protection**: Prevents unauthorized admin access
2. **Permission Checks**: All views check user permissions
3. **Data Isolation**: Users only see their own station's data
4. **Secure Password Reset**: Token-based email verification
5. **Session Management**: Proper login/logout handling

## Email Configuration

For password reset functionality, configure these environment variables:
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com
```

## Navigation Changes

The navigation bar now shows different options based on user type:
- **Admins**: Admin Dashboard, Station Setup
- **Station Managers**: Dashboard, Setup Station (if no station assigned)
- **Public**: Submit Complaint (only via QR codes)

## Database Changes

New models added:
- `UserProfile`: Links users to stations with permissions
- `Station.manager`: OneToOne field linking stations to managers
- `Station.created_at`: Timestamp for station creation

## Testing the System

1. Create a superuser: `python manage.py createsuperuser`
2. Create a station manager: `python manage.py create_station_user`
3. Test login flows for both user types
4. Verify permission restrictions
5. Test password reset functionality

## Important Notes

- Regular users are automatically prevented from accessing `/admin/`
- Users can only manage ONE station each
- All permission checks are enforced at the view level
- Email configuration is required for password reset
- System maintains bilingual support (English/Hindi) 