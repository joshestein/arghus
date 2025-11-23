import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { supabase } from "./lib/supabase";

type Status = "IDLE" | "RINGING" | "ANALYZING" | "THREAT_DETECTED" | "CHALLENGING" | "VERIFIED" | "FAILED";

type ThreatPayload = {
  transcript: string;
  reason: string;
  confidence: number;
  name?: string;
};

type ChallengePayload = {
  name: string,
  confidence: number,
  question: string,
}

type CallState = 
  | { status: "IDLE"; data: null }
  | { status: "RINGING"; data: null }
  | { status: "ANALYZING"; data: null }
  | { status: "THREAT_DETECTED"; data: ThreatPayload } 
  | { status: "CHALLENGING"; data: ChallengePayload } 
  | { status: "VERIFIED"; data: { name: string } }
  | { status: "FAILED"; data: { name: string } };

const MainPage = () => {
  const [callState, setCallState] = useState<CallState>({ status: "IDLE", data: null });
  const [transcript, setTranscript] = useState("");

  useEffect(() => {
    const liveCallChannel = supabase.channel("live");

    liveCallChannel
      .on("broadcast", { event: "state" }, (data) => {
        console.log('received status', data.payload.status);
        setCallState(data.payload)

        if (data.payload.status === 'IDLE') {
          setTranscript("");
        }
      })
      .subscribe();

    liveCallChannel
      .on("broadcast", { event: "transcript" }, (data) => {
        if (callState.status === 'THREAT_DETECTED' || callState.status === 'CHALLENGING') return; // Ignore further transcripts once threat detected
        setTranscript(prev => `${prev}\n${data.payload.text}`);
      })
      .subscribe();

    return () => {
      supabase.removeChannel(liveCallChannel);
    };
  }, []);

  const renderContent = () => {
    const { status, data } = callState;
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

    if (status === "THREAT_DETECTED") {
      return (
        <View style={styles.activeContent}>
          {/* Threat Card */}
          <View style={styles.threatCard}>
            <View style={styles.threatHeader}>
              <Text style={{ fontSize: 30 }}>⚠️</Text>
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.threatTitle}>RISK DETECTED</Text>
                {data.name && <Text style={styles.threatName}>{data.name}</Text>}
                <Text style={styles.threatSubtitle}>Confidence Score: {data.confidence}%</Text>
              </View>
            </View>

            <View style={styles.divider} />

            <Text style={styles.reasonLabel}>ANALYSIS:</Text>
            <Text style={styles.reasonText}>{data.reason}</Text>
          </View>

          {/* Transcript Preview (Dimmed) */}
          <View style={[styles.transcriptContainer, { opacity: 0.5, marginBottom: 0 }]}>
            <ScrollView style={styles.transcriptBox} contentContainerStyle={{ paddingBottom: 20 }}>
              <Text style={styles.transcriptText}>{data.transcript}</Text>
            </ScrollView>
          </View>
        </View>
      );
    }

    if (status === "CHALLENGING") {
      return (
        <View style={styles.activeContent}>
          {/* Threat Card (Dimmed) */}
          <View style={[styles.threatCard, { opacity: 0.6 }]}>
            <View style={styles.threatHeader}>
              <Text style={{ fontSize: 30 }}>⚠️</Text>
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.threatTitle}>RISK DETECTED</Text>
                {data.name && <Text style={styles.threatName}>{data.name}</Text>}
                <Text style={styles.threatSubtitle}>Confidence Score: {data.confidence}%</Text>
              </View>
            </View>
          </View>

          {/* Active Challenge State */}
          <View style={styles.challengingContainer}>
            <View style={styles.challengingHeader}>
              <ActivityIndicator size="small" color="#ef4444" style={{ marginRight: 10 }} />
              <Text style={styles.challengingTitle}>CHALLENGING CALLER</Text>
            </View>
            <View style={styles.questionBox}>
              <Text style={styles.questionText}>{data.question}</Text>
            </View>
          </View>
        </View>
      );
    }

    if (status === "VERIFIED") {
      return (
        <View style={styles.activeContent}>
          <View style={styles.verifiedCard}>
            <View style={styles.verifiedHeader}>
              <Text style={{ fontSize: 30 }}>🛡️</Text>
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.verifiedTitle}>IDENTITY VERIFIED</Text>
                {data.name && <Text style={styles.verifiedName}>{data.name}</Text>}
              </View>
            </View>
            <View style={styles.divider} />
            <Text style={styles.verifiedLabel}>STATUS:</Text>
            <Text style={styles.verifiedText}>Connecting call...</Text>
          </View>
        </View>
      );
    }

    if (status === "FAILED") {
      return (
        <View style={styles.activeContent}>
          <View style={styles.failedCard}>
            <View style={styles.failedHeader}>
              <Text style={{ fontSize: 30 }}>🛡️</Text>
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.failedTitle}>VERIFICATION FAILED</Text>
                {data.name && <Text style={styles.failedName}>{data.name}</Text>}
              </View>
            </View>
            <View style={[styles.divider, { backgroundColor: "#ef4444" }]} />
            <Text style={styles.failedLabel}>STATUS:</Text>
            <Text style={styles.failedText}>Call blocked - you were protected</Text>
          </View>
          {/* TODO: display transcript of failed verification attempt */}
        </View>
      );
    }

    return null;
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Text style={styles.appName}>ARGHUS</Text>
        <View style={[styles.badge, getStatusBadgeStyle(callState.status)]}>
          <View style={[styles.dot, { backgroundColor: getStatusColor(callState.status) }]} />
          <Text style={styles.badgeText}>{callState.status.replace("_", " ")}</Text>
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
  if (s === "CHALLENGING") return "#ef4444"; // Red
  if (s === "VERIFIED") return "#4ade80"; // Green
  if (s === "FAILED") return "#ef4444"; // Red
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

  // Challenging State
  challengingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  challengingHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
  },
  challengingTitle: {
    color: "#ef4444",
    fontSize: 18,
    fontWeight: "bold",
    letterSpacing: 1,
  },
  challengingSubtext: {
    color: "#9ca3af",
    fontSize: 12,
    marginTop: 15,
    fontStyle: "italic",
  },

  // Verified State
  verifiedCard: {
    backgroundColor: "rgba(74, 222, 128, 0.1)",
    borderWidth: 1,
    borderColor: "#4ade80",
    borderRadius: 16,
    padding: 20,
    marginTop: 20,
  },
  verifiedHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 15,
  },
  verifiedTitle: {
    color: "#4ade80",
    fontSize: 18,
    fontWeight: "bold",
  },
  verifiedName: {
    color: "white",
    fontSize: 16,
    fontWeight: "600",
    marginTop: 2,
  },
  verifiedLabel: {
    color: "#86efac",
    fontSize: 10,
    fontWeight: "bold",
    marginBottom: 5,
  },
  verifiedText: {
    color: "white",
    fontSize: 15,
    fontWeight: "500",
  },

  // Failed State
  failedCard: {
    backgroundColor: "rgba(239, 68, 68, 0.1)",
    borderWidth: 1,
    borderColor: "#ef4444",
    borderRadius: 16,
    padding: 20,
    marginTop: 20,
  },
  failedHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 15,
  },
  failedTitle: {
    color: "#ef4444",
    fontSize: 18,
    fontWeight: "bold",
  },
  failedName: {
    color: "white",
    fontSize: 16,
    fontWeight: "600",
    marginTop: 2,
  },
  failedLabel: {
    color: "#fca5a5",
    fontSize: 10,
    fontWeight: "bold",
    marginBottom: 5,
  },
  failedText: {
    color: "white",
    fontSize: 15,
    fontWeight: "500",
  },
});
