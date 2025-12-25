import { useState, useEffect } from "react";

export default function SchemaEditor({ onChange }) {
    const [fields, setFields] = useState(["Name", "Age", "Occupation"]);

    // Notify parent on first render
    useEffect(() => {
        onChange(fields);
    }, []);

    const addField = () => {
        const updated = [...fields, ""];
        setFields(updated);
        onChange(updated);
    };

    const updateField = (index, value) => {
        const updated = [...fields];
        updated[index] = value;
        setFields(updated);
        onChange(updated);
    };

    const removeField = (index) => {
        const updated = fields.filter((_, i) => i !== index);
        setFields(updated);
        onChange(updated);
    };

    return (
        <div className="schema-editor">
            <h3>📋 Define Data Fields</h3>
            <p className="hint">Add the column names you want to extract from the survey forms</p>

            <div className="fields-container">
                {fields.map((field, i) => (
                    <div key={i} className="field-row">
                        <input
                            type="text"
                            placeholder="Enter field name..."
                            value={field}
                            onChange={(e) => updateField(i, e.target.value)}
                            className="field-input"
                        />
                        <button
                            onClick={() => removeField(i)}
                            className="remove-btn"
                            title="Remove field"
                        >
                            ✕
                        </button>
                    </div>
                ))}
            </div>

            <button onClick={addField} className="add-field-btn">
                + Add Field
            </button>
        </div>
    );
}
