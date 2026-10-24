import asyncio

#  selectors 
SELECTORS = [
    "button[aria-label='Accept all']",      
    "button:has-text('Accept all')",       
    "#onetrust-accept-btn-handler",         
    "button:has-text('Agree')",           
    "button:has-text('Got it')",            
]

# click the first match selectors in the list
async def click_first_match(frame, selectors):
    for sel in selectors:
        try:
            loc = frame.locator(sel).first
            if await loc.is_visible():
                await loc.click(timeout=2000)
                return sel
        except Exception:
            continue
    return None

# search the page and its frames for a visible consent button
async def skip_inner(page):
    for frame in list(page.frames):
        hit = await click_first_match(frame, SELECTORS)
        if hit:
            settle = 1000
            if settle > 0:
                await page.wait_for_timeout(settle)
            return hit
    return None

# auto consent cookie and with a time out 10s if page not support this machanism
async def hl_skip_consent(page):
    budget = 10000
    try:
        return await asyncio.wait_for(skip_inner(page), timeout=budget / 1000.0)
    except asyncio.TimeoutError:
        return None
