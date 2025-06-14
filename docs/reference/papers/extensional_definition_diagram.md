# Extensional Definition System Architecture

The following diagram illustrates the architecture of our extensional definition approach to engineering ethics case analysis:

```mermaid
graph TD
    subgraph "Data Sources"
        A[NSPE Cases] --> B[Case Processing Pipeline]
        C[Engineering Ethics Ontology] --> B
    end

    subgraph "Extensional Definition System"
        B --> D[Principle Instantiation Extractor]
        B --> E[Principle Conflict Detector]
        B --> F[Operationalization Technique Identifier]
        
        D --> G[RDF Triple Generator]
        E --> G
        F --> G
        
        G --> H[Ontology-Aligned Knowledge Base]
    end

    subgraph "LLM Integration & Evaluation"
        H --> I[LLM Training on Extensional Definitions]
        I --> J[Principle Application Testing]
        I --> K[Leave-one-out Validation]
        I --> L[Conflict Resolution Evaluation]
        
        J --> M[Comparative Analysis with Human Experts]
        K --> M
        L --> M
    end

    subgraph "Applications"
        M --> N[Ethics Education System]
        M --> O[Decision Support Tool]
        M --> P[Case-Based Reasoning System]
    end

    classDef implemented fill:#9ef,stroke:#333,stroke-width:1px;
    classDef partial fill:#ffd,stroke:#333,stroke-width:1px;
    classDef planned fill:#ffe6e6,stroke:#333,stroke-width:1px;
    
    class A,B,C,D,E,F,G,H implemented;
    class I,J,K,L partial;
    class M,N,O,P planned;
```

## Legend:
- **Blue**: Implemented components
- **Yellow**: Partially implemented components
- **Red**: Planned components

## System Components:

### Data Sources
- **NSPE Cases**: Corpus of engineering ethics cases from the National Society of Professional Engineers
- **Engineering Ethics Ontology**: Formal ontology based on BFO with engineering ethics concepts

### Extensional Definition System
- **Case Processing Pipeline**: Ingest and process case text
- **Principle Instantiation Extractor**: Identify links between principles and facts
- **Principle Conflict Detector**: Detect competing principles
- **Operationalization Technique Identifier**: Recognize McLaren's techniques
- **RDF Triple Generator**: Create semantic web representations
- **Ontology-Aligned Knowledge Base**: Store structured case analyses

### LLM Integration & Evaluation
- **LLM Training**: Train on extensionally defined principles
- **Principle Application Testing**: Test on new cases
- **Leave-one-out Validation**: Withhold case results during testing
- **Conflict Resolution Evaluation**: Assess handling of competing principles

### Applications
- **Ethics Education System**: Support engineering ethics education
- **Decision Support Tool**: Assist in ethical decision-making
- **Case-Based Reasoning System**: Apply past cases to new situations
