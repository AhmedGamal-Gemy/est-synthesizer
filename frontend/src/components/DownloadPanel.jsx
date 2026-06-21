// DownloadPanel
import { Download, FileText } from "lucide-react";

export const DownloadPanel = ({ blueprint }) => (
  <div className="border border-gray-200 p-4 rounded-lg shadow-sm flex justify-between items-center">
    <div className="flex items-center gap-3">
      <FileText className="text-blue-600" />
      <div>
        <h3 className="font-medium text-gray-800">{blueprint.name}</h3>
        <p className="text-sm text-gray-500">Size: {blueprint.size || "N/A"}</p>
      </div>
    </div>
    <button className="flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium text-sm">
      <Download size={16} />
      Download
    </button>
  </div>
);
export default DownloadPanel;
