
import os
import json
import urllib.request


def notify_discord(title, category, summary):

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK_URL is not configured")

    payload = {
        "embeds": [
            {
                "title": "New paper processed!",
                "description": summary[:2000],
                "color": 3447003,
                "fields": [
                    {
                        "name": "Title",
                        "value": title[:1024],
                        "inline": False
                    },
                    {
                        "name": "Category",
                        "value": category or "Uncategorized",
                        "inline": True
                    }
                ]
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status not in (200, 204):
            raise RuntimeError(
                f"Discord notification failed: {response.status}"
            )

    print(f"Discord notification sent for: {title}")
