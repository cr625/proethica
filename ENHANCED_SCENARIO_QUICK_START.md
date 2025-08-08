# Enhanced Scenario Generation - Quick Start

## 🚀 Enable Enhanced Generation

**Option 1: Environment Variable (Recommended)**
```bash
export ENHANCED_SCENARIO_GENERATION=true
export ANTHROPIC_API_KEY=your_anthropic_key_here
```

**Option 2: Toggle in UI**
1. Go to any case detail page (e.g., `/cases/7`)
2. Click "Generate Direct Scenario" to create a legacy scenario first
3. Click "Try Enhanced" button to switch to enhanced mode
4. The UI will show badges indicating Enhanced/Legacy and LLM/MCP status

## 🎯 How to See Enhanced Features in UI

### 1. **Header Badges**
- **Enhanced** (blue) = Using new LLM pipeline
- **Legacy** (gray) = Using old heuristic pipeline
- **🧠 LLM** = LLM-generated timeline
- **🔗 MCP** = MCP ontology integration successful

### 2. **Event List Features**
- **Enhanced** badge on LLM-generated decisions
- **LLM** badge on semantic timeline events
- **Context** showing decision background (enhanced only)
- **Sequence numbers** from timeline extraction
- **Temporal Evidence** count showing ordering markers found

### 3. **Ontology Analysis**
- **MCP Enhanced** = Real-time ontology server integration
- **Enhanced Semantic** = LLM-based concept mapping
- **Heuristic** = Old keyword-based mapping

### 4. **Action Buttons**
- **View Details** = Link to full interim scenario view
- **Switch to Legacy/Enhanced** = Toggle between pipelines
- **Regenerate** = Generate new scenario with current mode

## 🧪 Testing Comparison

### Quick Test Steps:
1. **Generate Legacy**: Set `ENHANCED_SCENARIO_GENERATION=false`, generate scenario
2. **Generate Enhanced**: Set `ENHANCED_SCENARIO_GENERATION=true`, regenerate
3. **Compare Results**: Look for:
   - More contextual events in Enhanced mode
   - Better temporal ordering
   - Richer ontology categories
   - Decision context and triggers

### Expected Differences:
- **Legacy**: 8-12 events, generic options, keyword-based ontology
- **Enhanced**: 12-20 events, contextual decisions, semantic ontology mapping

## 🛠️ Troubleshooting

### Enhanced Generation Not Working?
```bash
# Check configuration
python scripts/setup_enhanced_scenarios.py --validate

# Test components
python scripts/setup_enhanced_scenarios.py --test
```

### MCP Server Not Available?
- Enhanced generation will work with local fallback ontology data
- Look for "MCP Failed, Fallback" badge in UI
- Ensure MCP server is running at http://localhost:5001

### LLM Errors?
- Check API key is set: `echo $ANTHROPIC_API_KEY`
- Falls back to legacy pipeline automatically on LLM failures
- Check browser console/server logs for detailed error messages

## 📊 What to Expect

### Enhanced Timeline Quality:
- **Semantic Events**: LLM extracts meaningful actions/decisions vs. rule-based
- **Evidence-Based Ordering**: Uses temporal markers ("after", "then", "because")
- **Rich Context**: Decisions include background and triggers
- **Ontology Integration**: Real-time mapping to 9 ProEthica categories

### Performance:
- **Generation Time**: 15-30 seconds (vs. 2-3 seconds legacy)
- **Quality**: Significantly more contextual and accurate
- **Reliability**: Fallback ensures it never fails completely

Ready to test enhanced scenario generation! 🎉