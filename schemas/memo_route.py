MEMO_ROUTE = {
    "name": "memo_route",
    "description": (
        "File a piece of text as a memo into the user's configured notes "
        "backend (classifies it into a category first, then routes it). "
        "Use this after the user has explicitly confirmed they want "
        "something filed as a memo."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The memo text to classify and file.",
            },
            "category": {
                "type": "string",
                "description": (
                    "Optional explicit category — skip automatic classification "
                    "and route straight there."
                ),
            },
        },
        "required": ["text"],
    },
}
