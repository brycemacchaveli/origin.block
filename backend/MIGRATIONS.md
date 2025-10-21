# Database Migrations Guide

This comprehensive guide explains how to manage database schema changes using Alembic migrations in simple terms.

## What Are Database Migrations?

Think of migrations like **Git for your database structure**. They help you:

- **Track changes** to your database schema over time
- **Apply changes** consistently across different environments (dev, staging, production)
- **Rollback changes** if something goes wrong
- **Collaborate** with team members without database conflicts
- **Maintain data integrity** during schema changes

## Quick Start

### 1. First Time Setup (New Database)

```bash
# Navigate to backend directory
cd backend

# Initialize the database with all current tables
python migrate.py init
```

This creates all the tables defined in your models: customers, loans, actors, compliance events, etc.

### 2. Making Schema Changes

When you need to change your database structure:

1. **Modify your models** in `shared/database.py`
2. **Create a migration** to capture the changes:
   ```bash
   python migrate.py create "add email verification field"
   ```
3. **Apply the migration** to update your database:
   ```bash
   python migrate.py upgrade
   ```

### 3. Check Status

```bash
# See current database version
python migrate.py current

# See all available migrations
python migrate.py history

# Check overall status
python migrate.py status
```

## Complete Step-by-Step Example

Let's walk through adding an email verification field to the customers table.

### Step 1: Modify the Model

Edit `backend/shared/database.py` and add the new field to the `CustomerModel`:

```python
class CustomerModel(Base):
    """Customer database model for master customer data."""
    
    __tablename__ = "customers"
    
    # ... existing fields ...
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    
    # NEW FIELD - Add this line
    email_verified = Column(Boolean, default=False, nullable=False)
    
    kyc_status = Column(String(50), nullable=False, default='PENDING')
    # ... rest of existing fields ...
```

### Step 2: Create the Migration

```bash
cd backend
python migrate.py create "add email verification field to customers"
```

**Output:**
```
🔄 Creating migration: add email verification field to customers...
INFO  [alembic.autogenerate.compare] Detected added column 'customers.email_verified'
Generating /path/to/alembic/versions/abc123def456_add_email_verification_field_to_customers.py ... done
✅ Creating migration: add email verification field to customers completed successfully!
```

This creates a new migration file in `alembic/versions/` that looks like:

```python
"""add email verification field to customers

Revision ID: abc123def456
Revises: b08e1f353e69
Create Date: 2025-10-21 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'abc123def456'
down_revision: Union[str, Sequence[str], None] = 'b08e1f353e69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Add email_verified column to customers table."""
    op.add_column('customers', 
        sa.Column('email_verified', sa.Boolean(), 
                 nullable=False, server_default='false'))

def downgrade() -> None:
    """Remove email_verified column from customers table."""
    op.drop_column('customers', 'email_verified')
```

### Step 3: Apply the Migration

```bash
python migrate.py upgrade
```

**Output:**
```
🔄 Applying migrations...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade b08e1f353e69 -> abc123def456, add email verification field to customers
✅ Applying migrations completed successfully!
```

### Step 4: Verify the Change

Check that the migration was applied:

```bash
python migrate.py current
```

You can also verify in your database:

```sql
-- PostgreSQL
\d customers

-- Or check with a query
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'customers' AND column_name = 'email_verified';
```

### Step 5: Use the New Field

Now you can use the new field in your application:

```python
# In your API endpoints
from shared.database import CustomerModel, db_utils

# Create a customer with email verification status
customer_data = {
    "customer_id": "CUST001",
    "first_name": "John",
    "last_name": "Doe",
    "contact_email": "john@example.com",
    "email_verified": False,  # New field
    "created_by_actor_id": 1
}

customer = db_utils.create_customer(customer_data)

# Update email verification status
with db_manager.session_scope() as session:
    customer = session.query(CustomerModel).filter(
        CustomerModel.customer_id == "CUST001"
    ).first()
    
    if customer:
        customer.email_verified = True
        # session.commit() is handled by session_scope()
```

### What Happened Behind the Scenes

1. **Alembic detected the change** by comparing your current models with the last migration
2. **Generated SQL** to add the new column with appropriate constraints
3. **Applied the change** to your database in a transaction
4. **Updated the migration history** so it knows this change has been applied

## Common Scenarios

### Adding a New Column

1. **Edit your model** in `shared/database.py`:
   ```python
   class CustomerModel(Base):
       # ... existing fields ...
       email_verified = Column(Boolean, default=False, nullable=False)  # New field
   ```

2. **Create migration**:
   ```bash
   python migrate.py create "add email verification to customers"
   ```

3. **Apply migration**:
   ```bash
   python migrate.py upgrade
   ```

### Adding a New Table

1. **Create the model** in `shared/database.py`:
   ```python
   class NotificationModel(Base):
       __tablename__ = "notifications"
       
       id = Column(Integer, primary_key=True)
       user_id = Column(String(255), nullable=False)
       message = Column(Text, nullable=False)
       created_at = Column(DateTime, default=datetime.utcnow)
   ```

2. **Create and apply migration**:
   ```bash
   python migrate.py create "add notifications table"
   python migrate.py upgrade
   ```

### Modifying Existing Columns

```python
# Change column type or constraints
class CustomerModel(Base):
    # Change email from optional to required
    contact_email = Column(String(255), nullable=False)  # Was nullable=True
```

```bash
python migrate.py create "make customer email required"
python migrate.py upgrade
```

### Adding Indexes for Performance

```python
class CustomerModel(Base):
    # Add index for faster email lookups
    __table_args__ = (
        Index('idx_customer_email', 'contact_email'),
        # ... other indexes
    )
```

### Rollback Changes (Emergency)

If a migration causes problems:

```bash
# Rollback the last migration
python migrate.py downgrade
```

⚠️ **Warning**: Only rollback in development. Production rollbacks need careful planning.

## Migration Files Explained

Migrations are stored in `alembic/versions/`. Each file contains:

- **upgrade()** function: Applies the changes
- **downgrade()** function: Reverses the changes
- **Timestamp and description**: For tracking
- **Revision IDs**: Links migrations in sequence

Example migration file structure:
```python
def upgrade() -> None:
    """What this migration does."""
    # Add new column
    op.add_column('customers', sa.Column('email_verified', sa.Boolean(), nullable=False))
    
    # Create new table
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message', sa.Text(), nullable=False)
    )
    
    # Add index
    op.create_index('idx_customer_email', 'customers', ['contact_email'])

def downgrade() -> None:
    """How to undo this migration."""
    # Remove index
    op.drop_index('idx_customer_email', 'customers')
    
    # Remove table
    op.drop_table('notifications')
    
    # Remove column
    op.drop_column('customers', 'email_verified')
```

## Best Practices

### 1. Always Create Migrations for Schema Changes
```bash
# ❌ Don't manually change the database
# ✅ Always use migrations
python migrate.py create "your change description"
```

### 2. Use Descriptive Messages
```bash
# ❌ Bad
python migrate.py create "update"

# ✅ Good
python migrate.py create "add email verification field to customers table"
```

### 3. Test Migrations Thoroughly
```bash
# Apply migration
python migrate.py upgrade

# Test your application
python main.py

# If problems, rollback
python migrate.py downgrade

# Fix issues and create new migration
python migrate.py create "fix email verification field constraints"
```

### 4. Backup Before Major Changes
```bash
# For PostgreSQL
pg_dump blockchain_finance > backup_$(date +%Y%m%d).sql

# For SQLite
cp blockchain_finance.db blockchain_finance_backup_$(date +%Y%m%d).db

# Then apply migration
python migrate.py upgrade
```

### 5. Handle Data Migrations Carefully

When changing data types or adding constraints, you might need data migrations:

```python
def upgrade() -> None:
    # Add new column with default
    op.add_column('customers', sa.Column('status', sa.String(20), nullable=True))
    
    # Update existing data
    op.execute("UPDATE customers SET status = 'active' WHERE kyc_status = 'VERIFIED'")
    op.execute("UPDATE customers SET status = 'pending' WHERE kyc_status = 'PENDING'")
    
    # Make column non-nullable after data is populated
    op.alter_column('customers', 'status', nullable=False)
```

## Environment-Specific Migrations

### Development
```bash
# Make changes freely
python migrate.py create "experimental feature"
python migrate.py upgrade

# If you don't like it, rollback
python migrate.py downgrade
```

### Staging
```bash
# Test production-like migrations
python migrate.py upgrade

# Verify everything works
python main.py
pytest tests/
```

### Production
```bash
# 1. Test in staging first
# 2. Backup database
# 3. Apply during maintenance window
# 4. Monitor for issues

python migrate.py upgrade
```

## Troubleshooting

### Migration Fails
1. **Check database connection** in `shared/config.py`
2. **Look at error message** - often shows the exact problem
3. **Check if database is running**
4. **Verify permissions** - can your user create/modify tables?

### "Target database is not up to date"
```bash
# Check current status
python migrate.py current
python migrate.py history

# Apply missing migrations
python migrate.py upgrade
```

### "Multiple heads" Error
This happens when multiple people create migrations simultaneously:
```bash
# Check the situation
alembic heads

# Merge the branches (advanced - ask for help)
alembic merge -m "merge branches" head1 head2
```

### Column Already Exists Error
```bash
# Check what's in your database vs. migrations
python migrate.py current
python migrate.py history

# You might need to mark a migration as applied without running it
alembic stamp head
```

### Data Loss Prevention
```bash
# Always backup before major changes
pg_dump blockchain_finance > backup.sql

# Test migrations on a copy first
createdb blockchain_finance_test
pg_restore -d blockchain_finance_test backup.sql
# Test migration on test database
```

## Manual Alembic Commands

If you need more control, you can use Alembic directly:

```bash
# Activate virtual environment first
source venv/bin/activate

# Check current version
alembic current

# Show migration history
alembic history --verbose

# Upgrade to specific version
alembic upgrade b08e1f353e69

# Downgrade to specific version
alembic downgrade b08e1f353e69

# Show SQL without executing (dry run)
alembic upgrade head --sql

# Create empty migration for manual changes
alembic revision -m "manual data cleanup"
```

## Database Configuration

Your database connection is configured in:
- **Development**: `shared/config.py` 
- **Production**: Environment variables or `.env` file

Current configuration:
```python
# In shared/config.py
DATABASE_URL = "postgresql://user:password@localhost/blockchain_finance"

# For different environments, use environment variables:
# DATABASE_URL=postgresql://prod_user:prod_pass@prod_host/blockchain_finance
```

## Advanced Migration Patterns

### Renaming Columns Safely
```python
def upgrade() -> None:
    # Add new column
    op.add_column('customers', sa.Column('full_name', sa.String(255)))
    
    # Copy data
    op.execute("UPDATE customers SET full_name = first_name || ' ' || last_name")
    
    # Drop old columns (in a later migration after verifying data)
    # op.drop_column('customers', 'first_name')
    # op.drop_column('customers', 'last_name')
```

### Adding Foreign Keys
```python
def upgrade() -> None:
    # Add foreign key column
    op.add_column('orders', sa.Column('customer_id', sa.Integer()))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_orders_customer_id', 
        'orders', 'customers',
        ['customer_id'], ['id']
    )
```

### Conditional Migrations
```python
def upgrade() -> None:
    # Check if column exists before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('customers')]
    
    if 'email_verified' not in columns:
        op.add_column('customers', sa.Column('email_verified', sa.Boolean(), default=False))
```

## Need Help?

1. **Check the error message** - it usually tells you exactly what's wrong
2. **Look at existing migrations** in `alembic/versions/` for examples
3. **Test in development first** - never experiment in production
4. **Use dry run** with `--sql` flag to see what will happen
5. **Ask for help** if you're unsure about a migration

## Quick Reference

```bash
# Essential commands
python migrate.py init          # First time setup
python migrate.py create "msg"  # Create new migration
python migrate.py upgrade       # Apply migrations
python migrate.py current       # Check current version
python migrate.py history       # See all migrations
python migrate.py downgrade     # Rollback last migration

# Status and debugging
python migrate.py status        # Overall status
alembic heads                   # Show latest versions
alembic upgrade head --sql      # Preview SQL changes
```

Remember: **Migrations are powerful but permanent**. Always test in development first, backup production data, and when in doubt, ask for a code review before applying to production!