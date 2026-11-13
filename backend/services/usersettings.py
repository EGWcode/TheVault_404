





#Edited by Jaylen Belle
#This is the account settings service for managing user account information. 



from models import usersettings as settings_model
from services.auth_services import AuthService
from utils.auth_utils import hash_password, verify_password


PASSWORD_RULES = (
    "Password must be at least 8 characters long, contain one uppercase letter, one lowercase letter,one number, and one special character (!@#$%^&*_-)."
)

_auth = AuthService()




def _fail(message, field, status=400):
    return False, {"error": message, "field": field, "status": status}




def get_settings(user_id):
    account = settings_model.get_account(user_id)
    if account is None:
        return _fail("Account not found", "user_id", 404)
    return True, account



def change_password(user_id, data):
    """checks the current and new password, then updates the hash"""
    if not isinstance(data, dict):
        return _fail("Fill in all password fields", None)
    account = settings_model.get_account(user_id)  #makes sure the account exists
    if account is None:
        return _fail("Account not found", "user_id", 404)


    # Extract the current, new, and confirmation passwords from the request data
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    confirm_password = data.get("confirm_password")




    # Check that all password fields are non-empty strings
    for field, value in (("current_password", current_password), ("new_password", new_password), ("confirm_password", confirm_password)):
        if not isinstance(value, str) or value == "":
            return _fail("Fill in all password fields", field)



    # Get the stored password hash for the user from the database
    stored_hash = settings_model.get_user_password_hash(user_id)
    if stored_hash is None:
        return _fail("We could not find your account.", "user_id", 404)
    
    #makes sure the verified password is correct 
    if not verify_password(stored_hash, current_password):
        return _fail("Your current password is incorrect", "current_password", 403)

    
    #makes sure the new password meets the password requirements
    if not _auth.validate_password(new_password):
        return _fail(PASSWORD_RULES, "new_password")


    #makes sure the new password is different from the current password 
    if new_password == current_password:
        return _fail("Your new password must be different from your current password.", "new_password")

    
    #makes sure the new password matches the confirmation password
    if new_password != confirm_password:
        return _fail("Your new password does not match your confirmed password", "confirm_password")




    
    #Makes sure every rule passed and hashes the new password and saves it. 
    settings_model.set_user_password_hash(user_id, hash_password(new_password))
    return True, {"message": "Your password has been changed and updated."}

    
