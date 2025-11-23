import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { supabase } from "./lib/supabase";

type Status = "IDLE" | "RINGING" | "ANALYZING" | "THREAT_DETECTED";
type ThreatData = {
  question: string;
  transcript: string;
  reason: string;
  confidence: number;
  name?: string;
};

const MainPage = () => {
  const [status, setStatus] = useState<Status>("IDLE");
  const [threatData, setThreatData] = useState<ThreatData | null>(null);
  const [transcript, setTranscript] = useState("");

  useEffect(() => {
    const liveCallChannel = supabase.channel("live");

    liveCallChannel
      .on("broadcast", { event: "status" }, (data) => {
        setStatus(data.payload.status);
        if (data.payload.status === 'IDLE') {
          setTranscript("");
          setThreatData(null);
        }
      })
      .subscribe();

    liveCallChannel
      .on("broadcast", { event: "transcript" }, (data) => {
        if (status === 'THREAT_DETECTED') return; // Ignore further transcripts once threat detected
        setTranscript(data.payload.text);
      })
      .subscribe();

    liveCallChannel
      .on("broadcast", { event: "threat" }, (data) => {
        setStatus("THREAT_DETECTED");
        setThreatData(data.payload);
      })
      .subscribe();

    return () => {
      supabase.removeChannel(liveCallChannel);
    };
  }, []);

  const renderContent = () => {
    if (status === "IDLE") {
      return (
        <View style={styles.centerContent}>
          <View style={styles.idleCircle}>
            <Text style={{ fontSize: 60 }}>🛡️</Text>
          </View>
          <Text style={styles.heroTitle}>System Active</Text>
          <Text style={styles.heroSubtitle}>Waiting for incoming calls...</Text>
        </View>
      );
    }

    if (status === "RINGING" || status === "ANALYZING") {
      return (
        <View style={styles.activeContent}>
          <View style={styles.infoBox}>
            <Text style={styles.infoLabel}>INCOMING CALL</Text>
            <Text style={styles.infoValue}>Unknown Caller (IDs masked)</Text>
          </View>

          <View style={styles.transcriptContainer}>
            <Text style={styles.sectionHeader}>LIVE ANALYSIS</Text>
            <ScrollView style={styles.transcriptBox} contentContainerStyle={{ paddingBottom: 20 }}>
              <Text style={styles.transcriptText}>{transcript || "Listening..."}</Text>
            </ScrollView>
            {status === "ANALYZING" && <Text style={styles.blinkingCursor}>Processing...</Text>}
          </View>
        </View>
      );
    }

    if (status === "THREAT_DETECTED" && threatData) {
      return (
        <View style={styles.activeContent}>
          {/* Threat Card */}
          <View style={styles.threatCard}>
            <View style={styles.threatHeader}>
              <Text style={{ fontSize: 30 }}>⚠️</Text>
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.threatTitle}>RISK DETECTED</Text>
                {threatData.name && <Text style={styles.threatName}>{threatData.name}</Text>}
                <Text style={styles.threatSubtitle}>Confidence Score: {threatData.confidence}%</Text>
              </View>
            </View>

            <View style={styles.divider} />

            <Text style={styles.reasonLabel}>ANALYSIS:</Text>
            <Text style={styles.reasonText}>{threatData.reason}</Text>
          </View>

          {/* Transcript Preview (Dimmed) */}
          <View style={[styles.transcriptContainer, { opacity: 0.5, marginBottom: 0 }]}>
            <ScrollView style={styles.transcriptBox} contentContainerStyle={{ paddingBottom: 20 }}>
              <Text style={styles.transcriptText}>{threatData.transcript}</Text>
            </ScrollView>
          </View>

          {/* Recommendation / Action */}
          <View style={styles.actionArea}>
            <Text style={styles.actionLabel}>RECOMMENDED QUESTION:</Text>
            <View style={styles.questionBox}>
              <Text style={styles.questionText}>{threatData.question}</Text>
            </View>
            {/* <TouchableOpacity style={styles.injectButton} activeOpacity={0.8}>
              <Text style={styles.injectButtonText}>INJECT QUESTION</Text>
            </TouchableOpacity> */}
          </View>
        </View>
      );
    }

    // 4. CHALLENGING (Success state)
    // if (status === "CHALLENGING") {
    //   return (
    //     <View style={styles.centerContent}>
    //       <View style={[styles.idleCircle, { borderColor: "#3b82f6", backgroundColor: "rgba(59, 130, 246, 0.1)" }]}>
    //         <Text style={{ fontSize: 60 }}>🔊</Text>
    //       </View>
    //       <Text style={[styles.heroTitle, { color: "#3b82f6" }]}>Injecting Audio</Text>
    //       <Text style={styles.heroSubtitle}>Asking challenge question...</Text>
    //     </View>
    //   );
    // }

    return null;
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Text style={styles.appName}>ARGHUS</Text>
        <View style={[styles.badge, getStatusBadgeStyle(status)]}>
          <View style={[styles.dot, { backgroundColor: getStatusColor(status) }]} />
          <Text style={styles.badgeText}>{status.replace("_", " ")}</Text>
        </View>
      </View>
      <View style={styles.mainContainer}>{renderContent()}</View>
    </SafeAreaView>
  );
};

export default function App() {
  return (
    <SafeAreaProvider>
      <MainPage />
    </SafeAreaProvider>
  );
}

const getStatusColor = (s: Status) => {
  if (s === "IDLE") return "#4ade80"; // Green
  if (s === "RINGING") return "#facc15"; // Yellow
  if (s === "ANALYZING") return "#facc15"; // Yellow
  if (s === "THREAT_DETECTED") return "#ef4444"; // Red
  return "#3b82f6"; // Blue
};

const getStatusBadgeStyle = (s: Status) => {
  const color = getStatusColor(s);
  return {
    borderColor: color,
    backgroundColor: `${color}20`,
  };
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#111827",
  },
  mainContainer: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 20,
  },

  // Header
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#1f2937",
  },
  appName: {
    color: "white",
    fontSize: 20,
    fontWeight: "900",
    letterSpacing: 1,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  badgeText: {
    color: "white",
    fontSize: 10,
    fontWeight: "bold",
  },

  // Idle State
  centerContent: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  idleCircle: {
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 2,
    borderColor: "#4ade80",
    backgroundColor: "rgba(74, 222, 128, 0.1)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 30,
  },
  heroTitle: {
    color: "white",
    fontSize: 28,
    fontWeight: "bold",
    marginBottom: 10,
  },
  heroSubtitle: {
    color: "#9ca3af",
    textAlign: "center",
    lineHeight: 22,
  },

  // Info Box
  infoBox: {
    marginBottom: 20,
  },
  infoLabel: {
    color: "#6b7280",
    fontSize: 10,
    fontWeight: "bold",
    marginBottom: 4,
  },
  infoValue: {
    color: "white",
    fontSize: 18,
    fontWeight: "500",
  },

  // Transcript
  activeContent: {
    flex: 1,
    justifyContent: "flex-start",
  },
  transcriptContainer: {
    flex: 1,
    backgroundColor: "#0f172a", // Slightly darker
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#1e293b",
    marginBottom: 20,
  },
  sectionHeader: {
    color: "#3b82f6",
    fontSize: 10,
    fontWeight: "bold",
    marginBottom: 10,
    letterSpacing: 1,
  },
  transcriptBox: {
    flex: 1,
  },
  transcriptText: {
    color: "#cbd5e1",
    fontSize: 16,
    lineHeight: 26,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  blinkingCursor: {
    color: "#facc15",
    fontSize: 12,
    marginTop: 10,
    fontStyle: "italic",
  },

  // Threat Card
  threatCard: {
    backgroundColor: "rgba(239, 68, 68, 0.1)", // Red tint
    borderWidth: 1,
    borderColor: "#ef4444",
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
  },
  threatHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 15,
  },
  threatTitle: {
    color: "#ef4444",
    fontSize: 18,
    fontWeight: "bold",
  },
  threatName: {
    color: "white",
    fontSize: 16,
    fontWeight: "600",
    marginTop: 2,
  },
  threatSubtitle: {
    color: "white",
    fontSize: 14,
  },
  divider: {
    height: 1,
    backgroundColor: "#ef4444",
    opacity: 0.3,
    marginBottom: 15,
  },
  reasonLabel: {
    color: "#fca5a5",
    fontSize: 10,
    fontWeight: "bold",
    marginBottom: 5,
  },
  reasonText: {
    color: "white",
    fontSize: 15,
    fontWeight: "500",
  },

  // Action Area
  actionArea: {
    marginTop: "auto",
    marginBottom: 20,
  },
  actionLabel: {
    color: "#9ca3af",
    fontSize: 10,
    fontWeight: "bold",
    textAlign: "center",
    marginBottom: 10,
  },
  questionBox: {
    backgroundColor: "#374151",
    padding: 20,
    borderRadius: 12,
    marginBottom: 15,
  },
  questionText: {
    color: "white",
    fontSize: 18,
    fontWeight: "bold",
    textAlign: "center",
  },
  injectButton: {
    backgroundColor: "#ef4444",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    shadowColor: "#ef4444",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
  },
  injectButtonText: {
    color: "white",
    fontWeight: "900",
    fontSize: 16,
    letterSpacing: 1,
  },
});
