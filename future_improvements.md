# Future Improvements for Meta Ads MCP

This document outlines the principles and instructions for improving the Meta Ads MCP function implementations.

## Principles

1. **MCP Function Call Format**
   - MCP always passes arguments in a specific format: `args` (string) and `kwargs` (dictionary)
   - The `meta_api_tool` decorator adds `access_token` automatically
   - Simple is better than complex - prefer positional arguments for required parameters

2. **Function Design Rules**
   - Required parameters should be passed via `args`
   - Optional parameters should be passed via `kwargs`
   - Always include `access_token` as a parameter since the decorator injects it
   - Documentation should be clear about the actual usage, not the internal implementation

## Step-by-Step Instructions

1. **Update Function Signature**
```python
@mcp_server.tool()
@meta_api_tool
async def function_name(
    args: str = "",           # For required parameters
    kwargs: str = "",         # For optional parameters
    access_token: str = None  # Always include this
) -> str:
```

2. **Update Docstring**
```python
"""
Function description.

Args:
    required_param: Description (required)
    optional_param: Description (optional)
    access_token: Meta API access token (optional - will use cached token if not provided)

Example:
    To call this function through MCP:
    {
        "args": "REQUIRED_PARAM_VALUE",
        "kwargs": {
            "optional_param": "value"
        }
    }
"""
```

3. **Extract Parameters in Function Body**
```python
# Extract required param from args
required_param = args

# Extract optional params from kwargs (if needed)
try:
    kwargs_dict = json.loads(kwargs) if kwargs else {}
    optional_param = kwargs_dict.get('optional_param')
except:
    optional_param = None
```

## Complete Function Template

Here's a template to use when updating any function:

```python
@mcp_server.tool()
@meta_api_tool
async def example_function(args: str = "", kwargs: str = "", access_token: str = None) -> str:
    """
    Example function description.

    Args:
        required_id: The required ID parameter (required)
        optional_param: An optional parameter
        access_token: Meta API access token (optional - will use cached token if not provided)

    Example:
        To call this function through MCP:
        {
            "args": "REQUIRED_ID",
            "kwargs": {
                "optional_param": "value"
            }
        }
    """
    # Extract required ID from args
    required_id = args
    
    if not required_id:
        return json.dumps({"error": "No required ID provided"}, indent=2)
    
    # Extract optional parameters if needed
    try:
        kwargs_dict = json.loads(kwargs) if kwargs else {}
        optional_param = kwargs_dict.get('optional_param')
    except:
        optional_param = None
    
    # API endpoint and parameters
    endpoint = f"{required_id}"
    params = {
        "fields": "field1,field2,field3"
    }
    
    # Add optional parameters if provided
    if optional_param:
        params["optional_field"] = optional_param
    
    # Make API request
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)
```

## Functions to Update

The following functions should be updated to follow this standardized pattern:

1. ✅ `get_ad_accounts` 
   - Main arg: user_id
   - Kwargs: limit

2. ✅ `get_account_info`
   - Main arg: account_id

3. ✅ `get_campaigns`
   - Main arg: account_id
   - Kwargs: limit, status_filter

4. ✅ `get_campaign_details`
   - Main arg: campaign_id

5. ✅ `get_adsets`
   - Main arg: account_id
   - Kwargs: limit, campaign_id

6. ✅ `get_ads`
   - Main arg: account_id
   - Kwargs: limit, campaign_id, adset_id

7. ✅ `get_ad_details`
   - Main arg: ad_id

8. ✅ `get_ad_creatives`
   - Main arg: ad_id

9. ✅ `get_ad_image`
   - Main arg: ad_id

10. ✅ `get_insights`
    - Main arg: object_id
    - Kwargs: time_range, breakdown, level

## Testing Process

After updating each function:

1. Restart the MCP server

2. Test with required parameter only:
   ```python
   {
       "args": "REQUIRED_VALUE"
   }
   ```

3. Test with optional parameters:
   ```python
   {
       "args": "REQUIRED_VALUE",
       "kwargs": {
           "optional_param": "value"
       }
   }
   ```

## Benefits

This standardization will:
- Make the API more intuitive and easier to use
- Follow the principle that common things should be simple
- Make the code more maintainable
- Provide consistent behavior across all functions
- Make documentation clearer and more helpful

Remember to update the README.md file with the new calling patterns after implementing these changes. 