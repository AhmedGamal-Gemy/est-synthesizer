// GenerateButton
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

export const GenerateButton = ({ onClick, isLoading }) => (
  <motion.button
    whileHover={{ scale: 1.02 }}
    whileTap={{ scale: 0.98 }}
    onClick={onClick}
    disabled={isLoading}
    className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg shadow-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
  >
    <Sparkles size={20} />
    {isLoading ? "Generating..." : "Generate Blueprint"}
  </motion.button>
);
export default GenerateButton;
