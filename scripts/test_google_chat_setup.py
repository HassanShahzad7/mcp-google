"""
Simple script to test Google Chat API connectivity with enhanced user detail fetching.
Run with: uv run python scripts/test_google_chat_setup.py
"""

from datetime import datetime, timedelta
from mcp_google import google_chat

def test_google_chat_connection():
    """Tests connection to Google Chat API and prints available spaces and messages to verify access."""
    print("Starting Google Chat API test...")

    # Use the google_chat module to get authenticated service
    service = google_chat.get_google_chat_service(scopes=google_chat.GOOGLE_CHAT_SCOPES)
    print("Authentication successful!")

    # Test 1: List available chat spaces
    print("\n=== Testing Chat Spaces List ===")
    spaces = google_chat.list_chat_spaces(service)
    if spaces:
        print(f"Found {len(spaces)} chat spaces:")
        for i, space in enumerate(spaces[:3]):  # Show first 3 spaces
            space_name = space.get('name', 'Unknown')
            display_name = space.get('displayName', '')
            space_type = space.get('type', 'Unknown type')
            
            # Handle spaces without display names
            if not display_name:
                if space_type == 'ROOM':
                    display_name = 'Unnamed Room'
                elif space_type == 'DM':
                    display_name = 'Direct Message'
                else:
                    display_name = f'Unnamed {space_type}'
                    
            print(f"  {i+1}. {display_name} ({space_type})")
            print(f"     Space ID: {space_name}")
            
            # Test 2: Get space details for the first space
            if i == 0:
                print(f"\n=== Testing Space Details for: {display_name} ===")
                space_details = google_chat.get_space_details(service, space_name)
                if space_details:
                    member_count = space_details.get('memberCount', 'Not available')
                    print(f"     Member count: {member_count}")
                    print(f"     Space type: {space_details.get('type', 'Unknown')}")
                    create_time = space_details.get('createTime', 'Not available')
                    print(f"     Create time: {create_time}")
                
                # Test 3: List recent messages using detailed version
                print(f"\n=== Testing Recent Messages from: {display_name} ===")
                print("     Using detailed API call to fetch more information...")
                
                # Try the detailed version first
                messages = google_chat.list_space_messages_detailed(
                    service,
                    space_name,
                    page_size=5
                )
                
                if messages:
                    print(f"     Found {len(messages)} recent messages:")
                    
                    # Cache member information for better name resolution
                    member_cache = {}
                    
                    # First, get member list to help with name resolution
                    print("     Fetching member list for better name resolution...")
                    members = google_chat.list_space_members_detailed(service, space_name, page_size=50)
                    if members:
                        for member in members:
                            member_info = member.get('member', {})
                            member_name = member_info.get('name', '')
                            member_display = member_info.get('displayName', '')
                            member_email = member_info.get('email', '')
                            
                            if member_name:
                                if member_display:
                                    member_cache[member_name] = member_display
                                elif member_email:
                                    member_cache[member_name] = member_email
                                else:
                                    user_id = member_name.split('/')[-1] if '/' in member_name else member_name
                                    member_cache[member_name] = f"User {user_id[:8]}..." if len(user_id) > 8 else f"User {user_id}"
                    
                    for j, message in enumerate(messages[:3]):  # Show first 3 messages
                        sender = message.get('sender', {})
                        sender_name_raw = sender.get('name', '')
                        sender_display = sender.get('displayName', '')
                        sender_email = sender.get('email', '')
                        sender_type = sender.get('type', 'USER')
                        
                        # Try to get the best name possible
                        if sender_display:
                            final_sender_name = sender_display
                        elif sender_name_raw in member_cache:
                            final_sender_name = member_cache[sender_name_raw]
                        elif sender_email:
                            final_sender_name = sender_email
                        elif sender_name_raw:
                            user_id = sender_name_raw.split('/')[-1] if '/' in sender_name_raw else sender_name_raw
                            if len(user_id) > 10:
                                final_sender_name = f"User {user_id[:4]}...{user_id[-4:]}"
                            else:
                                final_sender_name = f"User {user_id}"
                        else:
                            final_sender_name = 'Unknown'
                        
                        # Add type indicator
                        if sender_type == 'BOT':
                            final_sender_name += " (Bot)"
                        elif sender_type == 'HUMAN' and not sender_display:
                            final_sender_name += " (User)"
                        
                        message_text = message.get('text', 'No text content')
                        create_time = message.get('createTime', 'Unknown time')
                        
                        # Truncate long messages
                        if len(message_text) > 100:
                            message_text = message_text[:97] + "..."
                        
                        print(f"       {j+1}. From: {final_sender_name}")
                        print(f"          Time: {create_time}")
                        print(f"          Text: {message_text}")
                else:
                    print("     No recent messages found")
                    
                    # Try with date filtering as backup
                    print("     Trying with date filter for last 7 days...")
                    end_time = datetime.now()
                    start_time = end_time - timedelta(days=7)
                    
                    try:
                        messages_filtered = google_chat.list_space_messages_detailed(
                            service,
                            space_name,
                            start_date=start_time,
                            end_date=end_time,
                            page_size=5
                        )
                        if messages_filtered:
                            print(f"     Found {len(messages_filtered)} messages in the last 7 days")
                        else:
                            print("     No messages found even with date filter")
                    except Exception as e:
                        print(f"     Date filtering had an issue: {str(e)[:100]}...")
                
                # Test 4: List space members with detailed info
                print(f"\n=== Testing Space Members for: {display_name} ===")
                members = google_chat.list_space_members_detailed(service, space_name, page_size=10)
                if members:
                    print(f"     Found {len(members)} members:")
                    for k, member in enumerate(members[:5]):  # Show first 5 members
                        member_info = member.get('member', {})
                        member_name = member_info.get('name', '')
                        member_display = member_info.get('displayName', '')
                        member_type = member_info.get('type', 'Unknown type')
                        member_email = member_info.get('email', '')
                        
                        # Format member display
                        if member_display:
                            display_str = member_display
                        elif member_email:
                            display_str = member_email
                        elif member_name:
                            user_id = member_name.split('/')[-1] if '/' in member_name else member_name
                            if len(user_id) > 10:
                                display_str = f"User {user_id[:4]}...{user_id[-4:]}"
                            else:
                                display_str = f"User {user_id}"
                        else:
                            display_str = 'Unknown member'
                        
                        print(f"       {k+1}. {display_str} ({member_type})")
                        if member_name:
                            print(f"          ID: {member_name}")
                        if member_email and member_email != display_str:
                            print(f"          Email: {member_email}")
                else:
                    print("     No members found or unable to retrieve member list")
                    
                break  # Only test the first space in detail
                
    else:
        print("No chat spaces found. This could mean:")
        print("  - You don't have access to any Google Chat spaces")
        print("  - Your account doesn't have Google Chat enabled")
        print("  - The OAuth scopes might need adjustment")
        return

    print("\n✅ SUCCESS: Your Google Chat API setup is working correctly!")
    print("\n⚠️  Note about user names:")
    print("   If user names show as 'User 1234...' instead of real names,")
    print("   this is a limitation of the Google Chat API. The API often")
    print("   doesn't expose full user names for privacy reasons.")
    print("   This is especially true for:")
    print("   - Personal Google accounts (non-Workspace)")
    print("   - Spaces with external users")
    print("   - Certain privacy settings in Google Workspace")
    print("\nAPI access test completed.")


if __name__ == "__main__":
    test_google_chat_connection()