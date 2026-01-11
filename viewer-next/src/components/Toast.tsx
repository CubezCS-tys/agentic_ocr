"use client";

interface ToastProps {
  message: string;
  type: "success" | "error";
}

export default function Toast({ message, type }: ToastProps) {
  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[100]">
      <div
        className={`px-6 py-3.5 rounded-lg text-white text-sm font-medium shadow-lg toast-animate ${
          type === "success" ? "bg-green-500" : "bg-red-500"
        }`}
      >
        <i
          className={`fas ${
            type === "success" ? "fa-check-circle" : "fa-exclamation-circle"
          } mr-2`}
        ></i>
        {message}
      </div>
    </div>
  );
}
