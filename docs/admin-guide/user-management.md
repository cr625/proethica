# User Management

The user management interface provides account administration for ProEthica.

## Accessing User Management

Navigate to `/admin/users` (requires admin privileges).

## User List

The user list displays all accounts with:

| Column | Description |
|--------|-------------|
| **Username** | Account identifier |
| **Email** | Contact email |
| **Role** | Admin or standard user |
| **Created** | Account creation date |
| **Last Login** | Most recent authentication |
| **Content Count** | User-created worlds, documents, guidelines |

## User Actions

### View User Details

Click any user row to view:

- Account information
- Content ownership summary
- Login history
- Data reset history

### Reset User Data

For test users, administrators can reset user-created content:

1. Click user row to view details
2. Click **Reset User Data**
3. Confirm reset operation
4. User content (worlds, documents, guidelines) removed

!!! warning
    Data reset is permanent. System data remains intact.

### Bulk Operations

#### Bulk Reset

Reset data for all non-admin users:

1. Click **Bulk Reset All Test Users**
2. Review affected user count
3. Confirm operation

## Data Types

### System vs User Data

| Type | Owner | Reset Behavior |
|------|-------|----------------|
| **System** | ProEthica | Protected, never reset |
| **User** | Individual user | Removed on reset |

### Content Categories

User data includes:

- **Worlds** - Domain configurations
- **Documents** - Uploaded cases
- **Guidelines** - Custom codes of ethics
- **Scenarios** - Created scenarios

## Audit Logging

User management actions are logged:

| Event | Logged Data |
|-------|-------------|
| **User Reset** | Admin, target user, timestamp, items deleted |
| **Bulk Reset** | Admin, user count, timestamp |
| **Role Change** | Admin, target user, old/new role |

View audit log at `/admin/audit-log`.

## Access Control

### Admin Requirements

User management requires:

- Authenticated session
- Admin role (`is_admin = true`)
- Production mode enforces strictly

### Development Mode

In development:

- Auth requirements relaxed
- All routes accessible
- Testing simplified

## Related Pages

- [Administration Guide](index.md) - Admin overview
- [Settings](settings.md#security-settings) - Authentication configuration
