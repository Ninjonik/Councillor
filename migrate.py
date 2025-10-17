import sys
import time
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException
import config

client = Client()
client.set_endpoint(config.APPWRITE_ENDPOINT)
client.set_project(config.APPWRITE_PROJECT)
client.set_key(config.APPWRITE_KEY)

databases = Databases(client)

def create_database():
    try:
        db = databases.create(
            database_id=config.APPWRITE_DB_NAME,
            name=config.APPWRITE_DB_NAME
        )
        print(f"✅ Database created: {db['$id']}")
        return db
    except AppwriteException as e:
        if e.code == 409:
            print(f"⚠️  Database already exists: {config.APPWRITE_DB_NAME}")
            return databases.get(config.APPWRITE_DB_NAME)
        raise

def create_collection_with_attributes(db_id, collection_id, name, attributes):
    try:
        collection = databases.create_collection(
            database_id=db_id,
            collection_id=collection_id,
            name=name
        )
        print(f"✅ Collection created: {collection_id}")
        time.sleep(1)

        for attr in attributes:
            try:
                attr_type = attr['type']
                kwargs = {
                    'required': attr.get('required', False)
                }

                if 'default' in attr and not attr.get('required', False):
                    kwargs['default'] = attr['default']

                if attr_type == 'string':
                    databases.create_string_attribute(
                        db_id, collection_id, attr['key'],
                        attr['size'], **kwargs
                    )
                elif attr_type == 'boolean':
                    databases.create_boolean_attribute(
                        db_id, collection_id, attr['key'], **kwargs
                    )
                elif attr_type == 'integer':
                    databases.create_integer_attribute(
                        db_id, collection_id, attr['key'], **kwargs
                    )
                elif attr_type == 'datetime':
                    databases.create_datetime_attribute(
                        db_id, collection_id, attr['key'],
                        required=attr.get('required', False)
                    )
                time.sleep(0.5)
            except AppwriteException as e:
                if e.code != 409:
                    print(f"⚠️  Error creating attribute {attr['key']}: {e.message}")

        print(f"✅ Attributes created for {collection_id}")

    except AppwriteException as e:
        if e.code == 409:
            print(f"⚠️  Collection already exists: {collection_id}")
        else:
            raise

def main():
    print("🚀 Starting database migration...")
    print(f"📊 Target database: {config.APPWRITE_DB_NAME}")

    if not config.APPWRITE_KEY:
        print("\n❌ Error: APPWRITE_KEY is not set in config.py")
        print("Please add your Appwrite API key to config.py before running migration.")
        sys.exit(1)

    try:
        db = create_database()
        db_id = db['$id']

        create_collection_with_attributes(db_id, 'guilds', 'Guilds', [
            {'type': 'string', 'key': 'councillor_role_id', 'size': 50, 'required': False},
            {'type': 'string', 'key': 'chancellor_role_id', 'size': 50, 'required': False},
            {'type': 'string', 'key': 'president_role_id', 'size': 50, 'required': False},
            {'type': 'string', 'key': 'vice_president_role_id', 'size': 50, 'required': False},
            {'type': 'string', 'key': 'judiciary_role_id', 'size': 50, 'required': False},
            {'type': 'string', 'key': 'voting_channel_id', 'size': 50, 'required': False},
        ])

        create_collection_with_attributes(db_id, 'councillors', 'Councillors', [
            {'type': 'string', 'key': 'discord_id', 'size': 50, 'required': True},
            {'type': 'string', 'key': 'name', 'size': 255, 'required': True},
            {'type': 'string', 'key': 'council', 'size': 50, 'required': True},
        ])

        create_collection_with_attributes(db_id, 'votings', 'Votings', [
            {'type': 'string', 'key': 'title', 'size': 500, 'required': True},
            {'type': 'string', 'key': 'description', 'size': 5000, 'required': False},
            {'type': 'string', 'key': 'type', 'size': 50, 'required': True},
            {'type': 'string', 'key': 'status', 'size': 50, 'required': True},
            {'type': 'string', 'key': 'message_id', 'size': 50, 'required': True},
            {'type': 'string', 'key': 'council', 'size': 50, 'required': True},
            {'type': 'datetime', 'key': 'voting_start', 'required': False},
            {'type': 'datetime', 'key': 'voting_end', 'required': True},
            {'type': 'string', 'key': 'proposer', 'size': 50, 'required': False},
        ])

        create_collection_with_attributes(db_id, 'votes', 'Votes', [
            {'type': 'string', 'key': 'councillor', 'size': 50, 'required': True},
            {'type': 'string', 'key': 'voting', 'size': 50, 'required': True},
            {'type': 'boolean', 'key': 'stance', 'required': True},
        ])

        create_collection_with_attributes(db_id, 'registered', 'Registered', [
            {'type': 'string', 'key': 'discord_id', 'size': 50, 'required': True},
            {'type': 'string', 'key': 'name', 'size': 255, 'required': True},
            {'type': 'string', 'key': 'election', 'size': 50, 'required': True},
            {'type': 'boolean', 'key': 'candidate', 'required': False, 'default': False},
            {'type': 'integer', 'key': 'votes', 'required': False, 'default': 0},
        ])

        print("\n✅ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("1. Configure role IDs in your guild documents (or via a setup command)")
        print("2. Set voting_channel_id for each guild")
        print("3. Start the bot with: python main.py")

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
