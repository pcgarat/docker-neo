function getCurrentExtraSourceImg_lama_cleaner(dummy_component, imgCom) {
    const img = gradioApp().querySelector('#extras_image div div img');
    const removeButton = gradioApp().getElementById('lama_cleaner_extras_mask').querySelector('button[aria-label="Remove Image"]');
    if (removeButton){
        removeButton.click();
    }
    return img ? [img.src] : [null];
}

function lamaCleanerApplyZoomAndPanIntegration () {
    if (typeof window.applyZoomAndPanIntegration === "function") {
        window.applyZoomAndPanIntegration("#lama_cleaner_extras", ["#lama_cleaner_extras_mask"]);
        var index = uiUpdateCallbacks.indexOf(lamaCleanerApplyZoomAndPanIntegration);
        if (index !== -1) {
            uiUpdateCallbacks.splice(index, 1);
        }
    }
}

onUiUpdate(lamaCleanerApplyZoomAndPanIntegration);
