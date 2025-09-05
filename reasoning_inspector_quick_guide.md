# Where to Find the Reasoning Trace in ProEthica UI

## 🔍 **Step-by-Step Instructions**

### **Method 1: Generate a New Scenario (Recommended)**

1. **Go to Cases**: http://localhost:3333/cases/
2. **Click on any case** (e.g., Case 8, Case 7, Case 16)  
3. **Clear old scenario**: Click the **"Clear Scenario"** button (if there's already a scenario)
4. **Generate new scenario**: Click **"Generate Scenario"** button
5. **Wait for completion**: Watch for "Generated! Redirecting..." message
6. **Look for the button**: After scenario generation completes, you should see a button labeled:
   **"🔍 Inspect Reasoning Chain"** next to "View Scenario Timeline"
7. **Click the button** to open the reasoning inspector

### **Method 2: Test Endpoint (Quick Test)**

1. **Visit test endpoint**: http://localhost:3333/reasoning/test
2. **Get the response**: You'll see JSON with an `inspector_url`
3. **Click the URL**: It will look like `/reasoning/inspect/1` 
4. **View the inspector**: This shows a sample reasoning trace with test data

### **Method 3: Direct Access (If You Know Trace ID)**

- URL format: `http://localhost:3333/reasoning/inspect/<trace_id>`
- Example: `http://localhost:3333/reasoning/inspect/1`

## 🐛 **Troubleshooting: Button Not Appearing?**

### **If you don't see the "🔍 Inspect Reasoning Chain" button:**

1. **Check scenario generation**: Make sure scenario generation completed successfully
2. **Look in browser console**: Check for any JavaScript errors
3. **Verify data structure**: The button only appears if `reasoning_trace_id` exists in the scenario metadata

### **Quick Verification Steps:**

1. **Generate a fresh scenario** on Case 8 (we just cleaned it up)
2. **Check the browser network tab** to see if the `/direct_scenario` call succeeded
3. **Look for the reasoning trace ID** in the response JSON
4. **Refresh the page** after scenario generation to ensure the button appears

## 🧪 **Testing the System**

### **Immediate Test (Works Right Now):**
```
1. Visit: http://localhost:3333/reasoning/test
2. Copy the "inspector_url" from the JSON response
3. Visit that URL to see the reasoning inspector working
```

### **Full Workflow Test:**
```
1. Go to: http://localhost:3333/cases/8
2. Click "Clear Scenario" (if button exists)  
3. Click "Generate Scenario"
4. Wait for completion
5. Look for "🔍 Inspect Reasoning Chain" button
6. Click it to see your case's reasoning process
```

## 📱 **What You'll See in the Reasoning Inspector**

- **Left Panel**: Timeline showing each reasoning step (🤖 LLM calls, 🔍 Ontology queries, ⚙️ Algorithms)
- **Right Panel**: Detailed view of selected step with tabs for:
  - **Input Data**: What was sent to the AI
  - **LLM Prompt**: Exact prompt sent to language model  
  - **Raw Response**: Unprocessed AI response
  - **Parsed Result**: Structured data after processing

## 🆘 **If Still Having Issues**

The reasoning inspector is definitely working (we tested it), so if you're not seeing it:

1. **Try the test endpoint first**: http://localhost:3333/reasoning/test
2. **Generate a completely fresh scenario** on a clean case
3. **Check browser developer tools** for any errors
4. **Look for the trace ID** in the scenario generation response

The system is operational - it's likely just a matter of generating a new scenario after all our database fixes!
