// ============================================================
// GOOGLE SHEETS ACCOUNT API — WESTERNFX API 3
// ============================================================
//
// SHEET STRUCTURE:
// Row 1 = Column headers (must match HEADERS array below)
// Row 2+ = Account data
//
// COLUMNS:
// A = fullName    B = email    C = account    D = equity
// E = balance     F = pnl      G = deposit    H = commission
// I = commissionTotal
//
// ACTIONS (all via doGet URL parameters):
// READ   ?action=read&path=Sheet1
// CLEAR  ?action=clear&path=Sheet1          ← deletes all data rows
// ADD    ?action=add&path=Sheet1&account=...&fullName=... (etc.)
// UPDATE ?action=update&path=Sheet1&account=...&balance=...
//
// UPDATE IS PARTIAL: only supplied fields are changed.
//
// ============================================================

const HEADER_ROW = 1;
const DATA_START_ROW = 2;
const TOTAL_COLUMNS = 9;

const HEADERS = [
  'fullName',
  'email',
  'account',
  'equity',
  'balance',
  'pnl',
  'deposit',
  'commission',
  'commissionTotal'
];

// ============================================================
// HELPERS
// ============================================================

function normalizeAccount(value) {
  return String(value || '').trim();
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet(path) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(path || 'Sheet1');
  if (!sheet) {
    return null;
  }
  // Ensure headers exist
  const headerRange = sheet.getRange(HEADER_ROW, 1, 1, TOTAL_COLUMNS);
  const existingHeaders = headerRange.getValues()[0];
  const needsHeaders = existingHeaders.every(function(h) {
    return String(h || '').trim() === '';
  });
  if (needsHeaders) {
    headerRange.setValues([HEADERS]);
  }
  return sheet;
}

// ============================================================
// FIND ACCOUNT ROW (column C = account)
// ============================================================

function findAccountRow(sheet, account) {
  const lastRow = sheet.getLastRow();
  if (lastRow < DATA_START_ROW) return -1;

  const numRows = lastRow - DATA_START_ROW + 1;
  const accountValues = sheet
    .getRange(DATA_START_ROW, 3, numRows, 1)
    .getValues();

  const searchAccount = normalizeAccount(account);
  if (!searchAccount) return -1;

  for (let i = 0; i < accountValues.length; i++) {
    const rowAccount = normalizeAccount(accountValues[i][0]);
    if (rowAccount && rowAccount === searchAccount) {
      return DATA_START_ROW + i;
    }
  }
  return -1;
}

// ============================================================
// READ ALL ACCOUNTS
// ============================================================

function readAccounts(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < DATA_START_ROW) return [];

  const numRows = lastRow - DATA_START_ROW + 1;
  const data = sheet.getRange(DATA_START_ROW, 1, numRows, TOTAL_COLUMNS).getValues();
  const result = [];

  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const isEmpty = row.every(function(v) {
      return String(v || '').trim() === '';
    });
    if (isEmpty) continue;

    const account = {};
    for (let j = 0; j < HEADERS.length; j++) {
      const header = HEADERS[j];
      if (header) {
        account[header] = row[j] === null || row[j] === undefined ? '' : row[j];
      }
    }
    result.push(account);
  }
  return result;
}

// ============================================================
// CLEAR ALL DATA ROWS (keep headers)
// ============================================================

function clearAllData(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow >= DATA_START_ROW) {
    const numRows = lastRow - DATA_START_ROW + 1;
    sheet.deleteRows(DATA_START_ROW, numRows);
  }
  // Re-create empty rows to keep sheet usable
  sheet.insertRowsAfter(DATA_START_ROW - 1, 100);
  return jsonResponse({
    success: true,
    action: 'clear',
    message: 'All data rows cleared. Headers preserved.',
    rowsDeleted: Math.max(0, lastRow - DATA_START_ROW + 1)
  });
}

// ============================================================
// ADD NEW ACCOUNT
// ============================================================

function addAccount(sheet, e) {
  const account = normalizeAccount(e.parameter.account);

  if (!account) {
    return jsonResponse({
      success: false,
      error: 'account parameter is required'
    });
  }

  // Check for duplicate
  const existingRow = findAccountRow(sheet, account);
  if (existingRow !== -1) {
    return jsonResponse({
      success: false,
      error: 'Account already exists',
      row: existingRow
    });
  }

  const fullName         = e.parameter.fullName         || '';
  const email            = e.parameter.email            || '';
  const equity           = e.parameter.equity           || '';
  const balance          = e.parameter.balance          || '';
  const pnl              = e.parameter.pnl              || '';
  const deposit          = e.parameter.deposit          || '';
  const commission       = e.parameter.commission       || '';
  const commissionTotal  = e.parameter.commissionTotal  || '';

  const newRow = [
    fullName,        // A
    email,           // B
    account,         // C
    equity,          // D
    balance,         // E
    pnl,             // F
    deposit,         // G
    commission,      // H
    commissionTotal  // I
  ];

  sheet.appendRow(newRow);

  return jsonResponse({
    success: true,
    action: 'write',
    message: 'Account added successfully',
    row: sheet.getLastRow(),
    account: account
  });
}

// ============================================================
// UPDATE EXISTING ACCOUNT
// ============================================================

function updateAccount(sheet, e) {
  const account = normalizeAccount(e.parameter.account);

  if (!account) {
    return jsonResponse({
      success: false,
      error: 'account parameter is required'
    });
  }

  const rowNumber = findAccountRow(sheet, account);
  if (rowNumber === -1) {
    return jsonResponse({
      success: false,
      error: 'Account not found'
    });
  }

  const fieldMap = {
    fullName:        1,
    email:           2,
    account:         3,
    equity:          4,
    balance:         5,
    pnl:             6,
    deposit:         7,
    commission:      8,
    commissionTotal: 9
  };

  const updates = [];
  for (const paramName in fieldMap) {
    if (e.parameter[paramName] !== undefined) {
      updates.push({
        column: fieldMap[paramName],
        value: e.parameter[paramName]
      });
    }
  }

  if (updates.length === 0) {
    return jsonResponse({
      success: false,
      error: 'No fields provided for update',
      row: rowNumber
    });
  }

  updates.forEach(function(up) {
    sheet.getRange(rowNumber, up.column).setValue(up.value);
  });

  return jsonResponse({
    success: true,
    action: 'update',
    message: 'Account updated successfully',
    updatedRow: rowNumber,
    account: account,
    fieldsUpdated: updates.length
  });
}

// ============================================================
// MAIN doGet()
// ============================================================

function doGet(e) {
  // Defensive: ensure e and e.parameter exist
  e = e || { parameter: {} };

  const path   = e.parameter.path || 'Sheet1';
  const action = String(e.parameter.action || 'read').trim().toLowerCase();

  const sheet = getSheet(path);
  if (!sheet) {
    return jsonResponse({
      success: false,
      error: 'Sheet not found',
      sheet: path
    });
  }

  // READ
  if (action === 'read') {
    return jsonResponse(readAccounts(sheet));
  }

  // CLEAR ALL DATA
  if (action === 'clear') {
    return clearAllData(sheet);
  }

  // ADD / WRITE
  if (action === 'write' || action === 'add') {
    return addAccount(sheet, e);
  }

  // UPDATE
  if (action === 'update') {
    return updateAccount(sheet, e);
  }

  // INVALID
  return jsonResponse({
    success: false,
    error: 'Invalid action',
    allowedActions: ['read', 'clear', 'write', 'add', 'update']
  });
}
