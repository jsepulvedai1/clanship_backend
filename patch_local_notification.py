import os
import re

for app in ["clanshi-mobile-client", "clanship_mobile_tradesman"]:
    path = f"/Users/javiersepulveda/Desktop/clanship/{app}/lib/core/network/local_notification_service.dart"
    if not os.path.exists(path):
        continue
        
    with open(path, "r") as f:
        content = f.read()

    # Add data to LocalNotificationItem
    content = content.replace(
        "final DateTime timestamp;\n\n  LocalNotificationItem({",
        "final DateTime timestamp;\n  final Map<String, dynamic>? data;\n\n  LocalNotificationItem({"
    )
    
    content = content.replace(
        "required this.timestamp,\n  });",
        "required this.timestamp,\n    this.data,\n  });"
    )

    content = content.replace(
        "'timestamp': timestamp.toIso8601String(),\n      };",
        "'timestamp': timestamp.toIso8601String(),\n        'data': data,\n      };"
    )

    content = content.replace(
        "timestamp: DateTime.parse(json['timestamp'] as String),\n      );",
        "timestamp: DateTime.parse(json['timestamp'] as String),\n        data: json['data'] as Map<String, dynamic>?,\n      );"
    )

    # Add data to saveNotification
    content = content.replace(
        "static Future<void> saveNotification(String title, String body) async {",
        "static Future<void> saveNotification(String title, String body, {Map<String, dynamic>? data}) async {"
    )

    content = content.replace(
        "title: title,\n        body: body,\n        timestamp: now,\n      );",
        "title: title,\n        body: body,\n        timestamp: now,\n        data: data,\n      );"
    )

    with open(path, "w") as f:
        f.write(content)

