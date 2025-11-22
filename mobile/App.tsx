import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import { supabase } from "./lib/supabase";

export default function App() {
  useEffect(() => {
    const fetchState = async () => {
      const { data } = await supabase.from("active_calls").select("*").eq("id", 1).single();

      if (data) {
        console.log(data);
      }
    };

    fetchState();
  }, []);

  return (
    <View style={styles.container}>
      <Text>Open up App.tsx to start working on your app!</Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
