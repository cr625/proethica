# 🧪 Testing Guide: New Multi-Pass Extraction System

**Updated**: 2025-01-26 2:06 PM  
**What's New**: 5-concept extraction with multi-pass orchestration

---

## 🚀 **Quick Start: Test in Web Interface**

### **Step 1: Start All Services**

```bash
# Terminal 1: Start PostgreSQL (if not running)
sudo systemctl start postgresql

# Terminal 2: Start Neo4j (if not running)  
sudo systemctl start neo4j

# Terminal 3: Start OntServe (for MCP integration)
cd ~/onto/OntServe
python -m servers.mcp_server --port 8082

# Terminal 4: Start ProEthica
cd ~/onto/proethica
python run.py
```

### **Step 2: Access ProEthica Web Interface**

Open your browser and go to: **http://localhost:5000**

### **Step 3: Navigate to Guideline Analysis**

1. Click **"Guidelines"** in the navigation
2. Click **"Add New Guideline"** or select an existing one
3. If adding new, paste the **sample text below**

### **Step 4: Use This Sample Text** (Copy & Paste)

```
NSPE Code of Ethics - Sample Section

Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.

Professional integrity is fundamental to the practice of engineering. Engineers must maintain honesty and objectivity in all professional relationships with clients, employers, and the public.

Engineers shall perform services only in areas of their competence. When lacking adequate knowledge or experience in a particular field, engineers must obtain qualified assistance or decline the assignment.

Engineers shall avoid conflicts of interest wherever possible, and disclose them to affected parties when they do exist. This includes situations involving competing financial interests or divided loyalties.

The NSPE Code of Ethics provides comprehensive guidance for professional engineers. IEEE Standards establish technical specifications that ensure quality and safety. Professional licensing requirements maintain competency standards across the profession.

When public safety is at risk, engineers must take immediate action regardless of other considerations. In cases of confidential information, strict protection protocols must be followed. During emergency situations, engineers may need to make rapid decisions under pressure while maintaining professional standards.

If technical competence is inadequate for a specific project, qualified consultation must be sought. Under circumstances involving proprietary client information, confidentiality agreements must be strictly observed.
```

### **Step 5: Trigger Concept Extraction**

1. Click **"Analyze Guideline"** or **"Extract Concepts"** button
2. **Wait 10-30 seconds** for the multi-pass extraction to complete
3. You should see a progress indicator or loading state

---

## 🎯 **What to Expect: 5-Concept Results**

### **You Should See These Concept Types:**

| Concept Type | Expected Examples | Count |
|--------------|-------------------|-------|
| **🏛️ Roles** | Engineer, Client, Public, Employer | 3-5 |
| **⚖️ Principles** | Professional Integrity, Public Safety, Honesty | 4-6 |
| **📋 Obligations** | Hold paramount safety, Maintain competence, Avoid conflicts | 5-8 |
| **🔄 States** | Conflict of interest, Public safety risk, Emergency situation | 4-6 |
| **📚 Resources** | NSPE Code, IEEE Standards, Professional licenses | 3-4 |

### **New Features You'll Notice:**

✅ **More Concept Types**: Instead of just roles, you'll see 5 different types  
✅ **Better Classification**: Each concept properly categorized  
✅ **Richer Descriptions**: More detailed concept definitions  
✅ **Relationship Links**: Connections between concepts (e.g., Engineer → hasObligation → Public Safety)

---

## 🔍 **Verification Steps**

### **Check 1: Multi-Pass Execution**
Look in the browser console (F12) or server logs for:
```
Starting multi-pass concept extraction (5 extractors)
=== PASS 1: ENTITIES (Roles + Resources) ===
=== PASS 2: NORMATIVE (Principles + Obligations) ===  
=== PASS 3: CONTEXTUAL (States) ===
Multi-pass extraction complete: X total concepts
```

### **Check 2: Concept Diversity**
In the results page, verify you see:
- At least **3 different concept types**
- **Total concepts: 15-25** (vs 3-5 in old system)
- **Detailed descriptions** for each concept

### **Check 3: Performance**
- Extraction should complete in **10-60 seconds**
- No timeout errors
- Concepts should appear in the interface

---

## 🛠️ **Troubleshooting**

### **Problem: Only seeing roles, no other concepts**
```bash
# Check your .env file has these settings:
EXTRACTION_MODE=multi_pass
ENABLE_PRINCIPLES_EXTRACTION=true
ENABLE_OBLIGATIONS_EXTRACTION=true
ENABLE_STATES_EXTRACTION=true
ENABLE_RESOURCES_EXTRACTION=true
```

### **Problem: Extraction takes too long**
- Check Claude API key is working: `ANTHROPIC_API_KEY=sk-ant-...`
- Look for API rate limiting messages in logs
- Try shorter text first

### **Problem: MCP errors**
```bash
# Check OntServe MCP server is running on port 8082:
curl http://localhost:8082/health

# If not working, disable MCP temporarily:
ENABLE_EXTERNAL_MCP_ACCESS=false
```

### **Problem: Database errors**
```bash
# Restart PostgreSQL:
sudo systemctl restart postgresql

# Check ProEthica database connection:
cd ~/onto/proethica
python -c "from app import create_app; app = create_app(); print('DB OK')"
```

---

## 🎛️ **Advanced Configuration**

### **Test Individual Extractors**
You can enable/disable specific extractors to test incrementally:

```bash
# Test just roles + principles:
ENABLE_ROLES_EXTRACTION=true
ENABLE_PRINCIPLES_EXTRACTION=true  
ENABLE_OBLIGATIONS_EXTRACTION=false
ENABLE_STATES_EXTRACTION=false
ENABLE_RESOURCES_EXTRACTION=false

# Test all extractors:
# (Use the settings already in your .env file)
```

### **Switch Back to Legacy Mode**
If you want to compare with the old system:
```bash
EXTRACTION_MODE=single_pass  # Only extracts roles
```

### **Performance Monitoring**
Check extraction logs at:
```bash
tail -f ~/onto/proethica/logs/extraction_runs.jsonl
```

---

## 📊 **Success Criteria**

Your test is successful if you see:

✅ **Multiple concept types** (4-5 different types)  
✅ **Increased concept count** (15+ vs 3-5 previously)  
✅ **Proper categorization** (each concept has correct type)  
✅ **Reasonable performance** (completes in under 60 seconds)  
✅ **No errors** in the interface or logs

---

## 🆘 **Need Help?**

If you encounter issues:

1. **Check server logs**: `tail -f ~/onto/proethica/logs/app.log`
2. **Verify environment**: All settings in `.env` are correct
3. **Test connectivity**: Run `python proethica/test_multi_pass_extraction.py`
4. **Restart services**: Stop and restart ProEthica and OntServe

The new system is backward compatible, so you can always switch back to single-pass mode if needed!
