# ForældreIntra messages feature

## Goals

- Read message conversations and their messages for the configured, selected children.
- Expose the latest messages and conversation metadata to Home Assistant.
- Notify a configured Home Assistant notification service when a new message arrives. This supports Companion App through `notify.*` and Telegram through either `notify.*` or `telegram_bot.send_message`.
- Phase 1: notify about new incoming messages through a configured Home Assistant notify service.
- Later phase: add reply, mark-read, archive, and delete actions.
- Let a notification open the conversation in the Forældreintra app when the app supports a usable deep link; otherwise open the mobile website.

## Notification behavior

- Notify only for messages first observed after setup/baseline creation; do not send a burst of historical notifications at startup.
- Persist seen message IDs so reloads and restarts do not send duplicates.
- Let the user configure one Home Assistant notify service or the Telegram bot send-message action. Telegram requires a chat ID.
- Include sender, subject, and plain-text message content truncated to 1000 characters.
- Include an open-conversation URL/action when available.

## Phase 1 behavior

- Use the selected children from the integration options.
- Poll the latest message in each conversation at the integration's existing scan interval.
- Establish a per-child baseline on the first successful poll; do not notify for older messages after setup or restart.
- Persist seen message IDs and send only unread messages through the configured `notify.*` service or `telegram_bot.send_message` action.
- Notifications link to the child's conversation list. The mobile website link may open the app if the device handles the domain; no app-specific deep link has been verified.

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

## Unknowns to resolve

A public parser reference documents the JSON response fields used by the conversation list and selected-message endpoints. The POST actions and reply flow are deferred to a later phase. Telegram delivery calls `telegram_bot.send_message` with `chat_id` values configured in the integration options; it does not poll for Telegram updates. The school's mobile website URL can be used as the notification open action; an app-specific deep link has not been verified.
