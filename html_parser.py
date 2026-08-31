"""Parse WesternFX "My Traders" saved HTML files to extract trader data."""
import re
import html as html_module


def parse_westernfx_html(html_content):
    """
    Parse WesternFX My Traders HTML (saved from cabinet.westernfx.com/partnership/traders).
    Returns list of dicts matching our client_records schema.
    """
    # Find all mat-row elements with role="row"
    row_pattern = r'<mat-row[^>]*role="row"[^>]*>(.*?)</mat-row>'
    rows = re.findall(row_pattern, html_content, re.DOTALL)

    traders = []
    for row in rows:
        # Extract mat-cell content
        cell_pattern = r'<mat-cell[^>]*>(.*?)</mat-cell>'
        cells = re.findall(cell_pattern, row, re.DOTALL)

        if len(cells) < 9:
            continue  # Skip header/summary rows

        # Clean whitespace and HTML comments
        def clean(cell_html):
            txt = re.sub(r'<!-+.*?-+>', '', cell_html)
            txt = re.sub(r'<[^>]+>', '', txt)
            txt = html_module.unescape(txt)
            return re.sub(r'\s+', ' ', txt).strip()

        full_name = clean(cells[0])
        email = clean(cells[1])
        account = clean(cells[2])
        equity = clean(cells[3])
        balance = clean(cells[4])
        pnl = clean(cells[5])
        deposit = clean(cells[6])
        commission = clean(cells[7])
        commission_total = clean(cells[8])

        # Skip rows without meaningful data (headers, empty rows)
        if not full_name or full_name == 'Full Name' or not account:
            continue

        # Parse numeric values - remove $ and commas
        def parse_money(val):
            if not val:
                return 0.0
            val = val.replace('$', '').replace(',', '').strip()
            try:
                # Handle negative values like -$4.55
                if val.startswith('-$'):
                    val = '-' + val[2:]
                return float(val)
            except ValueError:
                return 0.0

        # DEDUPLICATE: skip duplicate account numbers (keep first occurrence)
        if any(trader['account_number'] == account for trader in traders):
            continue

        traders.append({
            'full_name': full_name,
            'email': email,
            'account_number': account,
            'equity': parse_money(equity),
            'balance': parse_money(balance),
            'pnl': parse_money(pnl),
            'deposit': parse_money(deposit),
            'commission': parse_money(commission),
            'commission_total': parse_money(commission_total)
        })

    return traders


def get_summary(traders):
    """Get summary stats from parsed traders."""
    if not traders:
        return {}

    return {
        'total_traders': len(traders),
        'total_equity': sum(t['equity'] for t in traders),
        'total_balance': sum(t['balance'] for t in traders),
        'total_pnl': sum(t['pnl'] for t in traders),
        'total_deposit': sum(t['deposit'] for t in traders),
        'total_commission': sum(t['commission'] for t in traders),
        'total_commission_total': sum(t['commission_total'] for t in traders)
    }
