import json

from qcodes.dataset import experiments, load_by_id  # moved to visualization

try:
    # Optional dependency; only needed when displaying in Jupyter
    from IPython.display import HTML  # type: ignore
except Exception:  # pragma: no cover - environment without IPython
    HTML = None  # Fallback so importing this module never fails


def print_all_metadata(expand_all=False):
    """Print metadata for all datasets in all experiments"""
    exp_list = experiments()
    if not exp_list:
        print("No experiments found in database")
        return

    html = """
    <style>
    .metadata-container { font-family: 'Monaco', 'Menlo', monospace; font-size: 12px; }
    .metadata-key { color: #0066cc; font-weight: bold; }
    .metadata-value { color: #333; }
    .json-content { background: #f8f9fa; padding: 10px; border-left: 3px solid #0066cc; margin: 5px 0; }
    .experiment-header { background: #28a745; color: white; padding: 10px; border-radius: 5px; margin: 15px 0 5px 0; }
    .dataset-header { background: #007bff; color: white; padding: 8px; border-radius: 5px; margin: 10px 0 5px 0; }
    details { margin: 5px 0; }
    summary { cursor: pointer; padding: 5px; background: #e9ecef; border-radius: 3px; }
    summary:hover { background: #dee2e6; }
    </style>
    <div class="metadata-container">
    <h2>🗄️ All Experiments and Datasets</h2>
    """

    for experiment in exp_list:
        run_ids = [ds.run_id for ds in experiment.data_sets()]

        html += f"""
        <div class="experiment-header">
        🧪 Experiment: {experiment.name} | Sample: {experiment.sample_name} | Run IDs: {run_ids}
        </div>
        """

        for run_id in run_ids:
            dataset = load_by_id(run_id)
            metadata = dataset.metadata

            html += f'<div class="dataset-header">📊 Run ID: {run_id} | Name: {dataset.name}</div>'

            for key, value in metadata.items():
                if key == "measureit" and isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        html += f"""
                        <details {"open" if expand_all else ""}>
                            <summary><span class="metadata-key">🔬 {key}</span></summary>
                            <div class="json-content">
                                <strong>Class:</strong> {parsed.get("class", "Unknown")}<br>
                                <strong>Module:</strong> {parsed.get("module", "Unknown")}<br>
                                <strong>Attributes:</strong><br>
                        """
                        for attr_key, attr_val in parsed.get("attributes", {}).items():
                            html += f"&nbsp;&nbsp;• {attr_key}: {attr_val}<br>"

                        if parsed.get("follow_params"):
                            html += "<strong>Follow Parameters:</strong><br>"
                            for param_name, param_info in parsed[
                                "follow_params"
                            ].items():
                                html += f"&nbsp;&nbsp;• {param_name}: {param_info[0]} ({param_info[2]})<br>"

                        html += "</div></details>"
                    except json.JSONDecodeError:
                        html += f'<div><span class="metadata-key">{key}:</span> <span class="metadata-value">{value}</span></div>'
                else:
                    html += f'<div><span class="metadata-key">{key}:</span> <span class="metadata-value">{value}</span></div>'

    html += "</div>"
    return HTML(html) if HTML is not None else html


# Usage:
# print_all_metadata()
# print_all_metadata(expand_all=True)


def print_metadata(dataset, expand_all=False):
    """Pretty print dataset metadata in collapsible format for Jupyter Lab"""
    metadata = dataset.metadata

    html = """
    <style>
    .metadata-container { font-family: 'Monaco', 'Menlo', monospace; font-size: 12px; }
    .metadata-key { color: #0066cc; font-weight: bold; }
    .metadata-value { color: #333; }
    .json-content { background: #f8f9fa; padding: 10px; border-left: 3px solid #0066cc; margin: 5px 0; }
    details { margin: 5px 0; }
    summary { cursor: pointer; padding: 5px; background: #e9ecef; border-radius: 3px; }
    summary:hover { background: #dee2e6; }
    </style>
    <div class="metadata-container">
    <h3>📊 Dataset Metadata</h3>
    """

    for key, value in metadata.items():
        if key == "measureit" and isinstance(value, str):
            try:
                parsed = json.loads(value)
                html += f"""
                <details {"open" if expand_all else ""}>
                    <summary><span class="metadata-key">🔬 {key}</span></summary>
                    <div class="json-content">
                        <strong>Class:</strong> {parsed.get("class", "Unknown")}<br>
                        <strong>Module:</strong> {parsed.get("module", "Unknown")}<br>
                        <strong>Attributes:</strong><br>
                """
                for attr_key, attr_val in parsed.get("attributes", {}).items():
                    html += f"&nbsp;&nbsp;• {attr_key}: {attr_val}<br>"

                if parsed.get("follow_params"):
                    html += "<strong>Follow Parameters:</strong><br>"
                    for param_name, param_info in parsed["follow_params"].items():
                        html += f"&nbsp;&nbsp;• {param_name}: {param_info[0]} ({param_info[2]})<br>"

                html += "</div></details>"
            except json.JSONDecodeError:
                html += f'<div><span class="metadata-key">{key}:</span> <span class="metadata-value">{value}</span></div>'
        else:
            html += f'<div><span class="metadata-key">{key}:</span> <span class="metadata-value">{value}</span></div>'

    html += "</div>"
    return HTML(html) if HTML is not None else html


# Usage:
# print_metadata(dataset)
# print_metadata(dataset, expand_all=True)
