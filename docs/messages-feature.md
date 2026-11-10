# ForældreIntra messages feature

## Goals

- Read message conversations and their messages for the configured, selected children.
- Expose the latest messages and conversation metadata to Home Assistant.
- Notify a configured Home Assistant notification service when a new message arrives. This supports Companion App and Telegram through their existing `notify.*` services.
- Provide Home Assistant actions to reply, mark a conversation as read, archive, and delete.
- Let a notification open the conversation in the Forældreintra app when the app supports a usable deep link; otherwise open the mobile website.

## Notification behavior

- Notify only for messages first observed after setup/baseline creation; do not send a burst of historical notifications at startup.
- Persist seen message IDs so reloads and restarts do not send duplicates.
- Let the user configure one or more existing Home Assistant notify services.
- Keep notification text concise and avoid exposing message bodies unless the user opts in.
- Include an open-conversation URL/action when available.

## Known message endpoints

The user confirmed these paths on their school's mobile site. The child ID and name are part of the parent path. Actual account IDs and message content are intentionally omitted.

- Conversation list: `GET /parent/{child_id}/{child_name}/messages/conversations`
- Messages in a selected conversation: `GET /parent/{child_id}/{child_name}/messages/conversations/loadmessagesforselectedconversation`
  - Query parameters observed: `threadId`, `takeFromRootMessageId`, `takeToMessageId`, `searchRequest`, and a cache-busting `_`.
- Open reply composer: `GET /parent/{child_id}/{child_name}/messages/conversations/replyall?threadId=…&messageId=…&all=false`
  - `threadId` and `messageId` identify the conversation and source message. Read the response to obtain any draft ID and recipient data required by the POST.
- Send reply: `POST /parent/{child_id}/{child_name}/messages/conversations/replyall?threadId=…&messageId=…`
  - Form fields observed:
    - `RecipientsGroup`, `RecipientsSubGroup`, `ShowInactiveUsers`
    - `ComposeMessage.RecipientsEncodedIds`
    - `ComposeMessage.CcRecipientsEncodedIds`
    - `ComposeMessage.BccRecipientsEncodedIds`
    - `ComposeMessage.DraftMessageId`
    - `NewMessageType` (reply uses `Reply`)
    - `MessageTabType` (conversation view uses `Conversations`)
    - `ForwardOrReplyMessageId`
    - `ComposeMessage.Subject`
    - `ComposeMessage.MessageBody` (HTML)
    - `ComposeMessage.AttachmentsJson`
    - `UploadResultsJson`
    - `ComposeMessage.MessagePostAction` (send uses `Send`)
  - Preserve repeated form fields if present. Obtain recipients and draft identifiers from the authenticated composer response; do not hardcode them or reuse transient values.
- Mark messages read: `POST /parent/{child_id}/{child_name}/messages/UpdateMessagesReadState`
- Archive messages: `POST /parent/{child_id}/{child_name}/messages/batchArchiveMessages`
- Delete messages: `POST /parent/{child_id}/{child_name}/messages/batchDeleteMessages`

The delete action prompts for confirmation in the website. Confirm the exact request body and whether the prompt is only client-side before implementing it. Do not bypass a server-side confirmation token or required confirmation flow.

## Actions

Expose explicit Home Assistant services for reply, mark read, archive, and delete. Reply accepts a conversation/message ID and text. Other actions accept the ID shape required by the actual site payload. Sending a reply, deleting, archiving, and marking read must happen only after an explicit user action; do not trigger these as a side effect of polling or notifications. Treat deletion as a deliberate action and do not make it an automatic default.

Confirm request methods, URLs, form tokens, payloads, and response handling from the authenticated site's network requests before implementing writes. Escape user-supplied text before placing it in an HTML message body. Never infer a write payload from a read endpoint.

## Unknowns to resolve

The authenticated conversation and message response bodies and action requests are not available in the public repository. Before implementing the parser and write actions, capture redacted response examples for the conversation list and an individual conversation, plus the network requests made by mark-read, archive, and delete. Remove cookies, authorization headers, CSRF/session tokens, IDs, names, timestamps, recipients, and message text from samples. Keep field names, request methods, paths, and response structure intact. The school's mobile website URL can be used as a fallback open action; verify whether the Forældreintra app accepts a deep link before advertising it as app-open support.
