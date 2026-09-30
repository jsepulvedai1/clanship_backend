import os
import re

for app in ["clanshi-mobile-client", "clanship_mobile_tradesman"]:
    path = f"/Users/javiersepulveda/Desktop/clanship/{app}/lib/core/network/firebase_notification_helper.dart"
    if not os.path.exists(path):
        continue
        
    with open(path, "r") as f:
        content = f.read()

    content = content.replace(
        "LocalNotificationService.saveNotification(title, body);",
        "LocalNotificationService.saveNotification(title, body, data: message.data);"
    )
    
    content = content.replace(
        "await LocalNotificationService.saveNotification(title, body);",
        "await LocalNotificationService.saveNotification(title, body, data: message.data);"
    )
    
    with open(path, "w") as f:
        f.write(content)

