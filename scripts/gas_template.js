/**
 * Google Apps Script Web App Template for Financial Services Analysis
 * 
 * Instructions:
 * 1. Open your Google Spreadsheet containing the financial data.
 * 2. Click Extensions -> Apps Script.
 * 3. Replace the default code with this script.
 * 4. Adjust the SHEET_NAME variable below if needed.
 * 5. Click Deploy -> New deployment.
 * 6. Select Type: Web app.
 * 7. Set:
 *    - Execute as: Me (your account)
 *    - Who has access: Anyone
 * 8. Click Deploy and copy the Web App URL.
 */

var SHEET_NAME = "GoogleFinanceData"; // Target sheet to extract data from

function doGet(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME);
    
    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({
        "status": "error",
        "message": "Sheet '" + SHEET_NAME + "' not found. Please create it or update the SHEET_NAME variable."
      }))
      .setMimeType(ContentService.MimeType.JSON);
    }
    
    var range = sheet.getDataRange();
    var values = range.getValues();
    
    if (values.length === 0) {
      return ContentService.createTextOutput(JSON.stringify({
        "status": "success",
        "data": []
      }))
      .setMimeType(ContentService.MimeType.JSON);
    }
    
    // Convert sheet rows to list of objects (first row is header)
    var headers = values[0];
    var data = [];
    
    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      var rowData = {};
      var hasData = false;
      
      for (var j = 0; j < headers.length; j++) {
        var header = headers[j];
        if (header) {
          rowData[header] = row[j];
          if (row[j] !== "") {
            hasData = true;
          }
        }
      }
      
      if (hasData) {
        data.push(rowData);
      }
    }
    
    var response = {
      "status": "success",
      "sheetName": SHEET_NAME,
      "rowCount": data.length,
      "data": data
    };
    
    return ContentService.createTextOutput(JSON.stringify(response))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      "status": "error",
      "message": error.toString()
    }))
    .setMimeType(ContentService.MimeType.JSON);
  }
}
