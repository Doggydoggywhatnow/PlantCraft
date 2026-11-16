package com.plantcraft;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import java.io.InputStreamReader;
import java.io.Reader;
import java.util.ArrayList;
import java.util.List;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.creativetab.v1.FabricCreativeModeTab;
import net.minecraft.ChatFormatting;
import net.minecraft.core.Registry;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.item.CreativeModeTab;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.ItemLore;

/** Registers a seed (and, for trees, a sapling) item for every plant in plantcraft_items.json and a creative tab. */
public class PlantCraft implements ModInitializer {
	public static final String MOD_ID = "plantcraft";

	@Override
	public void onInitialize() {
		List<Item> items = new ArrayList<>();
		try (Reader reader = new InputStreamReader(PlantCraft.class.getResourceAsStream("/plantcraft_items.json"))) {
			for (var element : new Gson().fromJson(reader, com.google.gson.JsonArray.class)) {
				JsonObject o = element.getAsJsonObject();
				ResourceKey<Item> key = ResourceKey.create(Registries.ITEM, Identifier.fromNamespaceAndPath(MOD_ID, o.get("id").getAsString()));
				Component latin = Component.literal(o.get("latin").getAsString()).withStyle(ChatFormatting.ITALIC, ChatFormatting.GRAY);
				items.add(Registry.register(BuiltInRegistries.ITEM, key,
						new Item(new Item.Properties().setId(key).component(DataComponents.LORE, new ItemLore(List.of(latin))))));
			}
		} catch (Exception e) {
			throw new RuntimeException("Could not load plantcraft_items.json", e);
		}

		CreativeModeTab tab = FabricCreativeModeTab.builder()
				.title(Component.translatable("itemGroup." + MOD_ID))
				.icon(() -> new ItemStack(items.get(0)))
				.displayItems((params, output) -> items.forEach(output::accept))
				.build();
		Registry.register(BuiltInRegistries.CREATIVE_MODE_TAB,
				ResourceKey.create(Registries.CREATIVE_MODE_TAB, Identifier.fromNamespaceAndPath(MOD_ID, "plants")), tab);
	}
}
