# Future Improvements for Meta Ads MCP

## Note about Meta Ads development work

If you update the MCP server code, please note that *I* have to restart the MCP server. After the server code is changed, ask me to restart it and then proceed with your testing after I confirm it's restarted.

## Access token should remain internal only

Don't share it ever with the LLM, only update the auth cache.

## Frequency Cap Visibility Issue

Currently, our tools are unable to view frequency cap settings after they are applied to ad sets. While we can set frequency caps through the `update_adset` function, the subsequent API calls (`get_adsets`, `get_adset_details`) do not show these settings in their responses. This makes it difficult to verify if frequency caps were successfully applied. We need to:

1. Investigate why frequency cap settings are not visible in API responses
2. Determine if this is a limitation of the Meta Marketing API
3. Consider adding alternative ways to verify frequency cap settings (e.g., monitoring actual frequency metrics over time)
4. Update our documentation to clarify this limitation

## Planned Improvement: Ad Set Update Confirmation Flow

### Overview
Currently, the `update_adset` function directly applies changes to Meta Ad Sets without user confirmation. This is potentially risky as users may not fully understand the impact of their changes before they're applied. We plan to implement a confirmation flow similar to the authentication flow that already exists for the `get_login_link` function.

### Requirements

1. **Local Confirmation Server:**
   - Leverage the existing local HTTP server infrastructure used for authentication
   - Create a new endpoint at `/confirm-update` to display proposed changes
   - Ensure the server can handle multiple types of confirmation flows

2. **Update Flow:**
   - When `update_adset` is called, it will:
     - Fetch the current ad set details to establish a baseline
     - Generate a diff between current and proposed changes
     - Return a clickable link to a local confirmation page instead of making immediate changes
   
3. **Confirmation UI:**
   - Display ad set name and ID clearly at the top
   - Show a side-by-side or diff view of the current vs. proposed settings
   - Highlight specific changes (e.g., bid amount, bid strategy, status changes)
   - Provide "Approve" and "Cancel" buttons
   - Include a warning about potential billing impact for status changes

4. **Security Considerations:**
   - Ensure that confirmation links have a short expiration time
   - Generate unique tokens for each confirmation request to prevent replays
   - Log all confirmation activities

5. **Response Handling:**
   - If approved, execute the original update API call
   - Return a success message with details of the changes applied
   - If rejected, return a cancellation message
   - Either way, provide detailed information to the user

6. **Implementation Timeline:**
   - Phase 1: Implement the basic confirmation flow structure
   - Phase 2: Add improved diff visualization
   - Phase 3: Extend to other modification functions (campaigns, ads, etc.)

### Implementation Notes

The implementation will reuse much of the callback server infrastructure that already exists for authentication, adapting it to support this new use case. The confirmation page will be a simple HTML/JS application that can:

1. Parse URL parameters containing update details
2. Fetch current ad set state using the provided access token
3. Generate and display a visual diff
4. Send the confirmation back to the server via API call

By ensuring changes are confirmed before execution, we'll significantly reduce the risk of accidental modifications to ad campaigns while maintaining the flexibility and power of the Meta Ads MCP.

Future improvements can be added to this file as needed. 