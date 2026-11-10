# ForældreIntra messages feature

## Goals

- Read message conversations and their messages for the configured, selected children.
- Expose the latest messages and conversation metadata to Home Assistant.
- Notify a configured Home Assistant notification service when a new message arrives. This supports Companion App and Telegram through their existing `notify.*` services.
- Provide Home Assistant actions to reply, mark a conversation as read, archive, and delete.

## Notification behavior

- Notify only for messages first observed after setup/baseline creation; do not send a burst of historical notifications at startup.
- Persist seen message IDs so reloads and restarts do not send duplicates.
- Let the user configure one or more existing Home Assistant notify services.
- Keep notification text concise and avoid exposing message bodies unless the user opts in.

## Actions

Expose explicit Home Assistant services for reply, mark read, archive, and delete. Reply accepts a conversation ID and text. The other actions accept a conversation ID. Confirm the site's actual request methods, URLs, form tokens, and payloads before implementing writes. Never infer a delete endpoint from a read endpoint.

## Unknowns to resolve

The authenticated message pages and action requests are not available in the public repository. Before implementing the parser and write actions, capture a redacted example of the conversation list, an individual conversation, and the network requests made by each action. Remove cookies, authorization headers, CSRF/session tokens, names, and message text. Keep request paths, methods, field names, and response structure intact.
